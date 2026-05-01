using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Avalonia.Media;
using ErpRagClient.Models;
using ErpRagClient.Services;
using System.Threading.Tasks;
using System;
using System.Threading;

namespace ErpRagClient.ViewModels;

public partial class MainViewModel : ObservableObject
{
    private readonly RagService _rag = new();
    private CancellationTokenSource? _cts;

    // ── Chat history ─────────────────────────────────────────────────
    public ObservableCollection<ChatMessage> Messages { get; } = [];

    // ── Bindable properties ──────────────────────────────────────────
    [ObservableProperty]
    private string _serverUrl = "http://localhost:8000";

    [ObservableProperty]
    private string _currentQuestion = string.Empty;

    [ObservableProperty]
    private bool _isLoading = false;

    [ObservableProperty]
    private string _healthText = "checking...";

    [ObservableProperty]
    private IBrush _healthColor = Brushes.Gray;

    [ObservableProperty]
    private string _healthInfo = string.Empty;

    [ObservableProperty]
    private string _statusMessage = string.Empty;

    // ── Computed for UI ──────────────────────────────────────────────
    public bool CanSend => !IsLoading && !string.IsNullOrWhiteSpace(CurrentQuestion);

    public bool HasMessages => Messages.Count > 0;

    public bool HasStatusMessage => !string.IsNullOrWhiteSpace(StatusMessage);

    partial void OnIsLoadingChanged(bool value)
    {
        OnPropertyChanged(nameof(CanSend));
        OnPropertyChanged(nameof(HasStatusMessage));
    }

    partial void OnCurrentQuestionChanged(string value) => OnPropertyChanged(nameof(CanSend));

    partial void OnStatusMessageChanged(string value) => OnPropertyChanged(nameof(HasStatusMessage));

    partial void OnServerUrlChanged(string value)
    {
        try { _rag.SetBaseUrl(value); }
        catch { }
    }

    public MainViewModel()
    {
        _rag.SetBaseUrl(_serverUrl);
        // Check health on startup
        _ = CheckHealthAsync();
    }

    // ── Send question command ─────────────────────────────────────────
    [RelayCommand(CanExecute = nameof(CanSend))]
    private async Task SendAsync()
    {
        var question = CurrentQuestion.Trim();
        if (string.IsNullOrEmpty(question)) return;

        // Add user message to chat
        Messages.Add(new ChatMessage
        {
            Role = MessageRole.User,
            Content = question,
        });
        OnPropertyChanged(nameof(HasMessages));

        CurrentQuestion = string.Empty;
        IsLoading = true;
        StatusMessage = "Searching ERP documentation...";

        _cts = new CancellationTokenSource();

        try
        {
            var response = await _rag.QueryAsync(question, _cts.Token);

            Messages.Add(new ChatMessage
            {
                Role = MessageRole.Assistant,
                Content = response.Answer,
                Sources = response.Sources,
                ChunksUsed = response.ChunksUsed,
            });

            StatusMessage = $"Found answer using {response.ChunksUsed} document chunks.";
        }
        catch (OperationCanceledException)
        {
            StatusMessage = "Request cancelled.";
        }
        catch (Exception ex)
        {
            Messages.Add(new ChatMessage
            {
                Role = MessageRole.Error,
                Content = $"Could not reach the server.\n\n{ex.Message}\n\nMake sure the RAG server is running at {ServerUrl}",
            });
            StatusMessage = "Error — check server connection.";
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(HasMessages));
        }
    }

    // ── Cancel in-flight request ─────────────────────────────────────
    [RelayCommand]
    private void Cancel()
    {
        _cts?.Cancel();
        IsLoading = false;
        StatusMessage = "Cancelled.";
    }

    // ── Health check ─────────────────────────────────────────────────
    [RelayCommand]
    private async Task CheckHealthAsync()
    {
        HealthText = "checking...";
        HealthColor = Brushes.Gray;
        HealthInfo = string.Empty;

        var health = await _rag.CheckHealthAsync();

        if (health is null || health.Status != "ok")
        {
            HealthText = "offline";
            HealthColor = Brushes.Red;
            HealthInfo = "Server unreachable. Start your RAG server first.";
        }
        else
        {
            HealthText = "online";
            HealthColor = Brushes.MediumSeaGreen;
            HealthInfo = $"{health.VectorsIndexed:N0} vectors · {health.LlmModel} · {health.VectorStore}";
        }
    }

    // ── Clear chat ───────────────────────────────────────────────────
    [RelayCommand]
    private void ClearChat()
    {
        Messages.Clear();
        StatusMessage = string.Empty;
        OnPropertyChanged(nameof(HasMessages));
    }
}