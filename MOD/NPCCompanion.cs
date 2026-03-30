// MOD/NPCCompanion.cs
// NPC companion that uses the RAG system to give contextual hints.
//
// The NPC hooks into the game's chat/dialog system and queries
// the RAG pipeline when the player speaks to them.
using Terraria;
using Terraria.ID;
using Terraria.GameContent;
using Terraria.ModLoader;
using Microsoft.Xna.Framework;
using System.Collections.Generic;

namespace TerrariaRAG;

public class NPCCompanion : ModNPC
{
    // NPC ID — choose a free NPC ID
    public const int NPC_ID = 999;

    public override string Texture => "TerrariaRAG/NPCCompanion";  // Place texture at this path

    public override void SetStaticDefaults()
    {
        Main.npcFrameCount[NPC_ID] = 25;
        NPCID.Sets.LowPriorityFramePriority[NPC_ID] = true;
        NPCID.Sets.TownNPCAnnualIncome[NPC_ID] = 0;  // No shop
    }

    public override void SetDefaults()
    {
        NPC.townNPC = true;
        NPC.friendly = true;
        NPC.width = 18;
        NPC.height = 40;
        NPC.aiStyle = NPCAIStyleID.Passive;
        NPC.damage = 0;
        NPC.defense = 0;
        NPC.lifeMax = 250;
        NPC.Hitbox = new Rectangle(0, 0, NPC.width, NPC.height);
        NPC.immortal = true;
        NPC.netAlways = true;
    }

    public override string GetChat()
    {
        // TODO: Query the RAG system with the player's current game state
        // and return a contextual hint.
        // Example:
        //   var gameState = GameStateTracker.GetCurrentState();
        //   var hint = RAGClient.Query("what should I do next?", gameState);
        //   return hint;
        return "I'm your guide! What would you like to know about Terraria?";
    }

    public override void SetChatButtons(ref string button1, ref string button2)
    {
        button1 = "Ask for a hint";
        button2 = "What's my progress?";
    }

    public override void OnChatButtonClicked(bool firstButton, ref string shopName)
    {
        if (firstButton)
        {
            // Main hint button — query RAG
            string hint = QueryRAGHint();
            Main.npcChatText = hint;
        }
        else
        {
            // Progress summary — describe current game state
            Main.npcChatText = GameStateTracker.GetProgressSummary();
        }
    }

    private string QueryRAGHint()
    {
        // TODO: Integrate with QUERY/query_engine.py via process or HTTP call
        // For now, return a placeholder
        var state = GameStateTracker.GetCurrentState();
        return $"I see you're in {state.CurrentBiome}. Current boss progress: {state.BossesDefeated.Count} bosses down. Ask me anything!";
    }

    public override void AI()
    {
        // Wander near the spawn point
        NPC.TargetClosest();
    }
}
