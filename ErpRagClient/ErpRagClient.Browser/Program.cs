using System.Runtime.Versioning;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Browser;
using ErpRagClient;

[assembly: SupportedOSPlatform("browser")]

// Browser/WebAssembly entry point
await BuildAvaloniaApp().StartBrowserAppAsync("out");
return;

static AppBuilder BuildAvaloniaApp()
    => AppBuilder.Configure<App>()
                 .WithInterFont();
