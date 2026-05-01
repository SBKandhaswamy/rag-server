using Avalonia;
using ErpRagClient;

// Desktop entry point — builds and runs the Avalonia app
BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
return;

static AppBuilder BuildAvaloniaApp()
    => AppBuilder.Configure<App>()
                 .UsePlatformDetect()
                 .WithInterFont()
                 .LogToTrace();
