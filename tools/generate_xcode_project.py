"""Generate the dependency-free Xcode project. Run after adding Swift source files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / 'iOS'
PROJECT = IOS / 'SpatialPointer.xcodeproj'


def identifier(name):
    return hashlib.sha1(name.encode()).hexdigest()[:24].upper()


def quote(value):
    return json.dumps(value, ensure_ascii=False)


def generate():
    sources = sorted((IOS / 'SpatialPointer').glob('*.swift')) + sorted(
        (IOS / 'SpatialPointerCore' / 'Sources' / 'SpatialPointerCore').glob('*.swift'))
    resources = [IOS / 'SpatialPointer' / 'Assets.xcassets', IOS / 'SpatialPointer' / 'PrivacyInfo.xcprivacy']
    files = sources + resources + [IOS / 'SpatialPointer' / 'Info.plist']
    objects = []

    def add(key, value):
        objects.append(f'\t\t{identifier(key)} = {{ {value} }};')

    for path in files:
        relative = path.relative_to(IOS).as_posix()
        file_type = ('sourcecode.swift' if path.suffix == '.swift' else 'folder.assetcatalog'
                     if path.suffix == '.xcassets' else 'text.xml')
        add('file:' + relative, f'isa = PBXFileReference; lastKnownFileType = {file_type}; path = {quote(relative)}; sourceTree = SOURCE_ROOT;')
        if path in sources or path in resources:
            add('build:' + relative, f'isa = PBXBuildFile; fileRef = {identifier("file:" + relative)};')

    source_ids = ', '.join(identifier('build:' + p.relative_to(IOS).as_posix()) for p in sources)
    resource_ids = ', '.join(identifier('build:' + p.relative_to(IOS).as_posix()) for p in resources)
    children = ', '.join(identifier('file:' + p.relative_to(IOS).as_posix()) for p in files)
    add('sources', f'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({source_ids},); runOnlyForDeploymentPostprocessing = 0;')
    add('resources', f'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = ({resource_ids},); runOnlyForDeploymentPostprocessing = 0;')
    add('frameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;')
    add('product', 'isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = SpatialPointer.app; sourceTree = BUILT_PRODUCTS_DIR;')
    add('products', f'isa = PBXGroup; children = ({identifier("product")},); name = Products; sourceTree = "<group>";')
    add('main', f'isa = PBXGroup; children = ({children}, {identifier("products")},); sourceTree = "<group>";')
    add('target', f'isa = PBXNativeTarget; buildConfigurationList = {identifier("target-configs")}; buildPhases = ({identifier("sources")}, {identifier("frameworks")}, {identifier("resources")},); buildRules = (); dependencies = (); name = SpatialPointer; productName = SpatialPointer; productReference = {identifier("product")}; productType = "com.apple.product-type.application";')
    add('project', f'isa = PBXProject; attributes = {{ BuildIndependentTargetsInParallel = YES; LastUpgradeCheck = 1600; TargetAttributes = {{ {identifier("target")} = {{ CreatedOnToolsVersion = 16.0; }}; }}; }}; buildConfigurationList = {identifier("project-configs")}; compatibilityVersion = "Xcode 14.0"; developmentRegion = ja; hasScannedForEncodings = 0; knownRegions = (ja, en, Base); mainGroup = {identifier("main")}; productRefGroup = {identifier("products")}; projectDirPath = ""; projectRoot = ""; targets = ({identifier("target")},);')

    for mode in ['Debug', 'Release']:
        project_settings = {'CLANG_ENABLE_MODULES': 'YES', 'CLANG_ENABLE_OBJC_ARC': 'YES',
                            'IPHONEOS_DEPLOYMENT_TARGET': '16.0', 'SDKROOT': 'iphoneos',
                            'SWIFT_VERSION': '5.0', 'ENABLE_USER_SCRIPT_SANDBOXING': 'YES',
                            'DEBUG_INFORMATION_FORMAT': 'dwarf' if mode == 'Debug' else 'dwarf-with-dsym'}
        target_settings = {'ASSETCATALOG_COMPILER_APPICON_NAME': 'AppIcon',
                           'CODE_SIGN_STYLE': 'Automatic', 'CURRENT_PROJECT_VERSION': '2',
                           'GENERATE_INFOPLIST_FILE': 'NO', 'INFOPLIST_FILE': 'SpatialPointer/Info.plist',
                           'MARKETING_VERSION': '0.2.1', 'PRODUCT_BUNDLE_IDENTIFIER': 'dev.yurashu2.spatialpointer',
                           'PRODUCT_NAME': '$(TARGET_NAME)', 'TARGETED_DEVICE_FAMILY': '1',
                           'SUPPORTED_PLATFORMS': 'iphoneos iphonesimulator',
                           'SUPPORTS_MACCATALYST': 'NO', 'SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD': 'NO',
                           'SWIFT_OPTIMIZATION_LEVEL': '-Onone' if mode == 'Debug' else '-O',
                           'LD_RUNPATH_SEARCH_PATHS': '$(inherited) @executable_path/Frameworks'}
        for scope, settings in [('project', project_settings), ('target', target_settings)]:
            settings_text = ' '.join(f'{key} = {quote(value)};' for key, value in settings.items())
            add(f'{scope}-{mode}', f'isa = XCBuildConfiguration; buildSettings = {{ {settings_text} }}; name = {mode};')
    for scope in ['project', 'target']:
        add(scope + '-configs', f'isa = XCConfigurationList; buildConfigurations = ({identifier(scope + "-Debug")}, {identifier(scope + "-Release")},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
    PROJECT.mkdir(parents=True, exist_ok=True)
    (PROJECT / 'project.pbxproj').write_text('// !$*UTF8*$!\n{\n\tarchiveVersion = 1;\n\tclasses = {};\n\tobjectVersion = 56;\n\tobjects = {\n' + '\n'.join(objects) + f'\n\t}};\n\trootObject = {identifier("project")};\n}}\n', encoding='utf-8')
    scheme_dir = PROJECT / 'xcshareddata' / 'xcschemes'
    scheme_dir.mkdir(parents=True, exist_ok=True)
    ref = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{identifier("target")}" BuildableName="SpatialPointer.app" BlueprintName="SpatialPointer" ReferencedContainer="container:SpatialPointer.xcodeproj"/>'
    (scheme_dir / 'SpatialPointer.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3">
  <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>
    <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{ref}</BuildActionEntry>
  </BuildActionEntries></BuildAction>
  <TestAction buildConfiguration="Debug" shouldUseLaunchSchemeArgsEnv="YES"><Testables/></TestAction>
  <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="NO"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></LaunchAction>
  <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{ref}</BuildableProductRunnable></ProfileAction>
  <AnalyzeAction buildConfiguration="Debug"/>
  <ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
''', encoding='utf-8')
    print(f'Generated Xcode project: {len(sources)} sources, {len(resources)} resources')


if __name__ == '__main__':
    generate()
