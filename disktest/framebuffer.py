"""Optional Linux true-color display. Only opens character display devices."""
import atexit
import ctypes as C
import os
import stat
import struct


class BitField(C.Structure):
    _fields_ = [('offset', C.c_uint32), ('length', C.c_uint32), ('msb_right', C.c_uint32)]


class Variable(C.Structure):
    _fields_ = [(key, C.c_uint32) for key in
                ('xres', 'yres', 'xres_virtual', 'yres_virtual', 'xoffset', 'yoffset',
                 'bits_per_pixel', 'grayscale')]
    _fields_ += [(key, BitField) for key in ('red', 'green', 'blue', 'transp')]
    _fields_ += [(key, C.c_uint32) for key in
                ('nonstd', 'activate', 'height', 'width', 'accel_flags', 'pixclock',
                 'left_margin', 'right_margin', 'upper_margin', 'lower_margin',
                 'hsync_len', 'vsync_len', 'sync', 'vmode', 'rotate', 'colorspace')]
    _fields_ += [('reserved', C.c_uint32*4)]


class Fixed(C.Structure):
    _fields_ = [('id', C.c_char*16), ('smem_start', C.c_ulong), ('smem_len', C.c_uint32),
                ('type', C.c_uint32), ('type_aux', C.c_uint32), ('visual', C.c_uint32),
                ('xpanstep', C.c_uint16), ('ypanstep', C.c_uint16), ('ywrapstep', C.c_uint16),
                ('line_length', C.c_uint32), ('mmio_start', C.c_ulong),
                ('mmio_len', C.c_uint32), ('accel', C.c_uint32),
                ('capabilities', C.c_uint16), ('reserved', C.c_uint16*2)]


def pixel_mode(var, fix):
    if fix.type != 0 or fix.visual != 2 or var.grayscale or var.nonstd:
        raise ValueError('Doğrudan renkli ekran biçimi desteklenmiyor.')
    if var.bits_per_pixel not in (24, 32):
        raise ValueError('Ekran 24/32 bit değil; metin görünümü kullanılacak.')
    if any(f.length != 8 or f.msb_right for f in (var.red, var.green, var.blue)):
        raise ValueError('Ekran renk kanalları desteklenmiyor.')
    offsets = (var.red.offset, var.green.offset, var.blue.offset)
    if offsets == (16, 8, 0):
        return 'BGRA' if var.bits_per_pixel == 32 else 'BGR'
    if offsets == (0, 8, 16):
        return 'RGBA' if var.bits_per_pixel == 32 else 'RGB'
    raise ValueError('Ekran kanal sırası desteklenmiyor.')


class Framebuffer:
    def __init__(self):
        import fcntl
        import mmap
        self.fb = self.tty = self.memory = None
        self.old_mode = None
        self.fcntl = fcntl
        try:
            self.fb = os.open('/dev/fb0', os.O_RDWR)
            info = os.fstat(self.fb)
            if not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 29:
                raise ValueError('Görüntü hedefi Linux ekran aygıtı değil.')
            variable = bytearray(C.sizeof(Variable))
            fixed = bytearray(C.sizeof(Fixed))
            fcntl.ioctl(self.fb, 0x4600, variable, True)
            fcntl.ioctl(self.fb, 0x4602, fixed, True)
            self.var, self.fix = Variable.from_buffer_copy(variable), Fixed.from_buffer_copy(fixed)
            self.mode = pixel_mode(self.var, self.fix)
            self.width, self.height = self.var.xres, self.var.yres
            if not (800 <= self.width <= 7680 and 480 <= self.height <= 4320):
                raise ValueError('Ekran boyutu grafik düzeni için uygun değil.')
            self.pixel_bytes = self.var.bits_per_pixel//8
            self.stride = self.fix.line_length
            self.offset = self.var.yoffset*self.stride + self.var.xoffset*self.pixel_bytes
            end = self.offset + (self.height-1)*self.stride + self.width*self.pixel_bytes
            if self.stride < self.width*self.pixel_bytes or end > self.fix.smem_len or self.fix.smem_len > 512*1024**2:
                raise ValueError('Ekran bellek sınırları doğrulanamadı.')
            self.memory = mmap.mmap(self.fb, self.fix.smem_len, mmap.MAP_SHARED,
                                    mmap.PROT_READ | mmap.PROT_WRITE)
            self.tty = os.open('/dev/tty1', os.O_RDWR | os.O_NOCTTY)
            mode = bytearray(4)
            fcntl.ioctl(self.tty, 0x4B3B, mode, True)
            self.old_mode = struct.unpack('i', mode)[0]
            fcntl.ioctl(self.tty, 0x4B3A, 1)  # KD_GRAPHICS; keyboard/Ctrl+C remains on tty1.
            atexit.register(self.close)
        except BaseException:
            self.close()
            raise

    def present(self, image):
        from PIL import Image
        state = bytearray(6)
        self.fcntl.ioctl(self.tty, 0x5603, state, True)
        if struct.unpack_from('H', state)[0] != 1:
            return  # Never paint over another virtual terminal.
        if image.size != (self.width, self.height):
            scale = min(self.width/image.width, self.height/image.height)
            resized = image.resize((int(image.width*scale), int(image.height*scale)), Image.Resampling.LANCZOS)
            image = Image.new('RGB', (self.width, self.height), '#0B1423')
            image.paste(resized, ((self.width-resized.width)//2, (self.height-resized.height)//2))
        data = image.convert('RGBA' if self.pixel_bytes == 4 else 'RGB').tobytes('raw', self.mode)
        row_size = self.width*self.pixel_bytes
        if self.stride == row_size:
            self.memory[self.offset:self.offset+len(data)] = data
        else:
            for y in range(self.height):
                offset = self.offset + y*self.stride
                self.memory[offset:offset+row_size] = data[y*row_size:(y+1)*row_size]

    def close(self):
        if self.tty is not None:
            if self.old_mode is not None:
                try:
                    self.fcntl.ioctl(self.tty, 0x4B3A, self.old_mode)
                except OSError:
                    pass
            os.close(self.tty)
            self.tty = None
        if self.memory is not None:
            self.memory.close()
            self.memory = None
        if self.fb is not None:
            os.close(self.fb)
            self.fb = None
