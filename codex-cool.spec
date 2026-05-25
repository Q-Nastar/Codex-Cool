import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('src/codex_cool/frontend', 'codex_cool/frontend'),
] + collect_data_files('webview')

hiddenimports = collect_submodules('codex_cool') + collect_submodules('webview') + [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'httpx',
    'h11',
    'anyio',
    'sniffio',
    'pydantic',
    'pydantic_core',
    'yaml',
    'click',
    'rich',
    'codex_cool.injector',
    'codex_cool.converters',
    'codex_cool.converters.anthropic_chat',
    'codex_cool.converters.responses_chat',
    'codex_cool.converters.stream',
    'codex_cool.models',
    'codex_cool.models.anthropic',
    'codex_cool.models.chat',
    'codex_cool.models.responses',
    'codex_cool.proxy',
    'codex_cool.proxy.router',
    'email.mime.multipart',
    'email.mime.text',
]

if sys.platform == 'darwin':
    hiddenimports += [
        'pyobjc',
        'pyobjc.core',
        'pyobjc.framework.Cocoa',
        'pyobjc.framework.WebKit',
        'pyobjc.framework.Quartz',
        'pyobjc.framework.Security',
        'pyobjc.framework.UniformTypeIdentifiers',
        'objc',
    ]

a = Analysis(
    ['src/codex_cool/desktop.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'PIL', 'cv2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Codex Cool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Codex Cool',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Codex Cool.app',
        icon=None,
        bundle_identifier='com.codex-cool.app',
        version='0.1.0',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'CFBundleName': 'Codex Cool',
            'CFBundleDisplayName': 'Codex Cool',
            'CFBundleIdentifier': 'com.codex-cool.app',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15',
            'NSAppTransportSecurity': {
                'NSAllowsLocalNetworking': True,
                'NSAllowsArbitraryLoads': True,
            },
            'LSUIElement': False,
            'NSPrincipalClass': 'NSApplication',
        },
    )
