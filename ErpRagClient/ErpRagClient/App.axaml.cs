using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using ErpRagClient.ViewModels;
using ErpRagClient.Views;

namespace ErpRagClient;

public class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        var vm = new MainViewModel();

        switch (ApplicationLifetime)
        {
            // ── Desktop ──────────────────────────────────────────────
            case IClassicDesktopStyleApplicationLifetime desktop:
                desktop.MainWindow = new Window
                {
                    Title          = "ERP Assistant",
                    Width          = 860,
                    Height         = 680,
                    MinWidth       = 360,
                    MinHeight      = 500,
                    Content        = new MainView { DataContext = vm },
                    WindowStartupLocation = WindowStartupLocation.CenterScreen,
                };
                break;

            // ── Browser / Mobile (single view) ───────────────────────
            case ISingleViewApplicationLifetime single:
                single.MainView = new MainView { DataContext = vm };
                break;
        }

        base.OnFrameworkInitializationCompleted();
    }
}
