"""Public references shared by machine-readable and human-readable reports."""
PROJECT_URL = 'https://github.com/nusretcankarakus/VEDT'
REPORT_GUIDE = PROJECT_URL + '/blob/main/docs/RAPOR-REHBERI-V1.md'
AI_GUIDE = PROJECT_URL + '/blob/main/docs/YAPAY-ZEKA-ILE-YORUMLAMA.md'
REPORT_SCHEMA_VERSION = 1


def references(version):
    return {'project_url': PROJECT_URL, 'report_guide_url': REPORT_GUIDE,
            'ai_guide_url': AI_GUIDE, 'report_schema_version': REPORT_SCHEMA_VERSION,
            'software_version': version}

PROJECT_NAME = 'VEDT'
PROJECT_FULL_NAME = 'Vektron Elektronik Disk Test'
