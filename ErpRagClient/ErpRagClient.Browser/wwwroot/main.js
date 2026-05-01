import { dotnet } from './_framework/dotnet.js'

const { setModuleImports, getAssemblyExports } = await dotnet
    .withApplicationArgumentsFromQuery()
    .bootstrap();

setModuleImports('main.js', {
    window: {
        location: {
            href: () => globalThis.window.location.href
        }
    }
});

globalThis.window.getAssemblyExports = getAssemblyExports;
