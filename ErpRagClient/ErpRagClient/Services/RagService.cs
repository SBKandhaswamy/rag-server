using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using ErpRagClient.Models;

namespace ErpRagClient.Services;

public class RagService
{
    private readonly HttpClient _http;

    private static readonly JsonSerializerOptions _json = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public RagService()
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(120) };
    }

    // ── Update base URL when user changes the server field ───────────
    public void SetBaseUrl(string url)
    {
        var clean = url.TrimEnd('/');
        _http.BaseAddress = new Uri(clean + "/");
    }

    // ── POST /query ───────────────────────────────────────────────────
    public async Task<QueryResponse> QueryAsync(string question, CancellationToken ct = default)
    {
        var payload = new QueryRequest(question);
        var response = await _http.PostAsJsonAsync("query", payload, _json, ct);

        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<QueryResponse>(_json, ct);
        return result ?? throw new InvalidOperationException("Empty response from server.");
    }

    // ── GET /health ───────────────────────────────────────────────────
    public async Task<HealthResponse?> CheckHealthAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync("health", ct);
            if (!response.IsSuccessStatusCode) return null;
            return await response.Content.ReadFromJsonAsync<HealthResponse>(_json, ct);
        }
        catch
        {
            return null;   // server unreachable
        }
    }
}