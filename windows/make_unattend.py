"""Prepare documented Windows OOBE settings; does not install or activate Windows."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NS = 'urn:schemas-microsoft-com:unattend'
WCM = 'http://schemas.microsoft.com/WMIConfig/2002/State'
ET.register_namespace('', NS)
ET.register_namespace('wcm', WCM)


def create(computer_name='VEDT', account_name='VEDT1'):
    if not re.fullmatch(r'VEDT[1-9][0-9]{0,14}', account_name):
        raise ValueError('Geçersiz VEDT hesap numarası.')
    if not re.fullmatch(r'[A-Z][A-Z0-9-]{0,14}', computer_name):
        raise ValueError('Geçersiz bilgisayar adı.')
    def element(parent, tag, text=None, **attributes):
        node = ET.SubElement(parent, '{' + NS + '}' + tag, attributes)
        if text is not None:
            node.text = str(text)
        return node
    def component(parent, name):
        return element(parent, 'component', name=name, processorArchitecture='amd64',
                       publicKeyToken='31bf3856ad364e35', language='neutral', versionScope='nonSxS')
    root = ET.Element('{' + NS + '}unattend')
    specialize = element(root, 'settings', **{'pass': 'specialize'})
    shell = component(specialize, 'Microsoft-Windows-Shell-Setup')
    element(shell, 'ComputerName', computer_name)
    element(shell, 'TimeZone', 'Turkey Standard Time')
    oobe = element(root, 'settings', **{'pass': 'oobeSystem'})
    locale = component(oobe, 'Microsoft-Windows-International-Core')
    for name, value in [('InputLocale', '041f:0000041f'), ('SystemLocale', 'tr-TR'),
                        ('UILanguage', 'tr-TR'), ('UserLocale', 'tr-TR')]:
        element(locale, name, value)
    shell = component(oobe, 'Microsoft-Windows-Shell-Setup')
    account = element(element(element(shell, 'UserAccounts'), 'LocalAccounts'), 'LocalAccount',
                      **{'{' + WCM + '}action': 'add'})
    element(account, 'Name', account_name)
    element(account, 'DisplayName', account_name)
    element(account, 'Description', 'VEDT geçici test hesabı')
    element(account, 'Group', 'Administrators')
    password = element(account, 'Password')
    element(password, 'Value', '')
    element(password, 'PlainText', 'true')
    login = element(shell, 'AutoLogon')
    element(login, 'Username', account_name)
    element(login, 'Domain', computer_name)
    element(login, 'Enabled', 'true')
    element(login, 'LogonCount', '1')
    password = element(login, 'Password')
    element(password, 'Value', '')
    element(password, 'PlainText', 'true')
    screens = element(shell, 'OOBE')
    for name in ('HideEULAPage', 'HideOEMRegistrationScreen', 'HideOnlineAccountScreens', 'HideWirelessSetupInOOBE'):
        element(screens, name, 'true')
    element(screens, 'ProtectYourPC', '3')
    command = element(element(shell, 'FirstLogonCommands'), 'SynchronousCommand',
                      **{'{' + WCM + '}action': 'add'})
    element(command, 'Order', '1')
    element(command, 'CommandLine', r'cmd.exe /c "%ProgramData%\DiskTest86\Complete-FirstLogon.cmd"')
    element(command, 'Description', 'VEDT masaüstü ve rapor hazırlığı')
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--computer-name', default='VEDT')
    parser.add_argument('--account-name', default='VEDT1')
    args = parser.parse_args()
    with args.output.open('xb') as stream:
        stream.write(create(args.computer_name, args.account_name))
