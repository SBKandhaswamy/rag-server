# ERP RAG Client — Avalonia UI

A cross-platform frontend for the ERP RAG server.
Runs on **Windows, macOS, Linux** (desktop) and **any browser** (WebAssembly).

---

## Prerequisites

Install .NET 8 SDK:
- Download from: https://dotnet.microsoft.com/download/dotnet/8.0
- Verify: `dotnet --version`  (must be 8.x)

Install Avalonia templates:
```
dotnet new install Avalonia.Templates
```

---

## Run on Desktop (Windows / macOS / Linux)

```cmd
cd ErpRagClient.Desktop
dotnet run
```

The app window opens. Make sure your RAG server is running at http://localhost:8000.

---

## Run in Browser (WebAssembly)

```cmd
cd ErpRagClient.Browser
dotnet run
```

Then open http://localhost:5000 in your browser.

Note: For browser mode, your RAG server must have CORS enabled (it already does
if you followed the guide — CORSMiddleware is configured to allow all origins).

---

## Build release (Desktop)

```cmd
cd ErpRagClient.Desktop
dotnet publish -c Release -r win-x64 --self-contained
```

Output is in: bin\Release\net8.0\win-x64\publish\

For other platforms replace win-x64 with:
- linux-x64   (Linux)
- osx-x64     (Intel Mac)
- osx-arm64   (Apple Silicon Mac)

---

## Project structure

```
ErpRagClient/
├── ErpRagClient/               Shared code (UI + logic)
│   ├── Models/
│   │   └── RagModels.cs        DTOs matching FastAPI responses
│   ├── Services/
│   │   └── RagService.cs       HTTP client for RAG server
│   ├── ViewModels/
│   │   └── MainViewModel.cs    All UI state + commands
│   └── Views/
│       └── MainView.axaml      The complete UI layout
│       └── MainView.axaml.cs   Code-behind (minimal)
│
├── ErpRagClient.Desktop/       Windows/macOS/Linux entry point
│   └── Program.cs
│
└── ErpRagClient.Browser/       WebAssembly entry point
    └── Program.cs
```

---

## Changing the server URL

The server URL defaults to http://localhost:8000. You can change it in
the header of the app — it updates live and the connection is re-tested.

---

## Adding mobile support (Android / iOS)

Install workloads:
```
dotnet workload install android ios
```

Create mobile project:
```
dotnet new avalonia.android -o ErpRagClient.Android
dotnet new avalonia.ios    -o ErpRagClient.iOS
```

Add project reference to ErpRagClient (shared) in each mobile .csproj.
The shared MainView and MainViewModel work without modification.
