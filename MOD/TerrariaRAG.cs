// MOD/TerrariaRAG.cs
// tModLoader integration entry point for Terraria RAG.
//
// This class is the main mod class. It initializes the RAG system,
// registers the NPC companion, and hooks into Terraria's game state.
using Terraria.ModLoader;

namespace TerrariaRAG;

public class TerrariaRAG : Mod
{
    public static TerrariaRAG Instance { get; private set; }

    // Shared HTTP client for querying Qdrant at runtime
    // private static HttpClient _qdrantClient;

    public override void Load()
    {
        Instance = this;
        // TODO: Initialize Qdrant HTTP client here
        // TODO: Register NPC companion
        // TODO: Hook into game state events
    }

    public override void Unload()
    {
        Instance = null;
        // TODO: Cleanup HTTP client
    }
}
