using System;
using System.Collections.Generic;

namespace ErpRagClient.Models;

// ── Request sent to POST /query ──────────────────────────────────────
public record QueryRequest(string Question);

// ── Source document returned in response ─────────────────────────────
public record SourceDoc(string File, int? Page)
{
    public string DisplayText => Page.HasValue ? $"{File} p.{Page}" : File;
}

// ── Full response from POST /query ───────────────────────────────────
public record QueryResponse(string Answer, List<SourceDoc> Sources, int ChunksUsed);

// ── Health check response from GET /health ───────────────────────────
public record HealthResponse(
    string Status,
    int VectorsIndexed,
    string LlmModel,
    string EmbeddingModel,
    string VectorStore
);

// ── A single chat message shown in the UI ────────────────────────────
public class ChatMessage
{
    public MessageRole Role { get; init; }
    public string Content { get; init; } = string.Empty;
    public List<SourceDoc> Sources { get; init; } = [];
    public int ChunksUsed { get; init; }
    public DateTime Timestamp { get; init; } = DateTime.Now;

    // Convenience helpers used by XAML bindings
    public bool IsUser => Role == MessageRole.User;

    public bool IsAssistant => Role == MessageRole.Assistant;
    public bool IsError => Role == MessageRole.Error;
    public bool HasSources => Sources.Count > 0;

    public string TimeLabel => Timestamp.ToString("HH:mm");
}

public enum MessageRole
{ User, Assistant, Error }