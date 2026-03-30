// MOD/GameStateTracker.cs
// Tracks the player's current game state for RAG filtering.
//
// Hooks into Terraria events to detect:
// - Current biomes
// - Bosses defeated
// - Armor / weapons tier
// - Hardmode status
// - Progression milestones
using Terraria;
using Terraria.ID;
using System.Collections.Generic;
using System.Linq;

namespace TerrariaRAG;

public static class GameStateTracker
{
    // Cached state — updated on game events
    private static bool _isHardmode = false;
    private static bool _moonLordDefeated = false;
    private static string _currentBiome = "Surface";
    private static HashSet<string> _bossesDefeated = new();
    private static string _armorTier = "Iron";
    private static string _weaponsTier = "Iron";
    private static List<string> _currentNPCs = new();

    // Boss name → boss key mapping
    private static readonly Dictionary<string, int> BossToNPCID = new()
    {
        {"Slime King", NPCID.KingSlime},
        {"Eye of Cthulhu", NPCID.EyeofCthulhu},
        {"Eater of Worlds", NPCID.EaterofWorldsHead},
        {"Brain of Cthulhu", NPCID.BrainofCthulhu},
        {"Queen Bee", NPCID.QueenBee},
        {"Skeletron", NPCID.SkeletronHead},
        {"Wall of Flesh", NPCID.WallofFlesh},
        {"Destroyer", NPCID.TheDestroyer},
        {"Twins", NPCID.Retinazer},
        {"Skeletron Prime", NPCID.SkeletronPrime},
        {"Plantera", NPCID.Plantera},
        {"Golem", NPCID.Golem},
        {"Duke Fishron", NPCID.DukeFishron},
        {"Cultist", NPCID.CultistBoss},
        {"Moon Lord", NPCID.MoonLordCore},
    };

    // Known armor tiers by set bonus
    private static readonly string[] ArmorTierOrder = {
        "Wood", "Copper", "Iron", "Silver", "Gold", "Platinum",
        "Meteor", "Shadow", "Crimson", "Molten", "Necro",
        "Jungle", "Diamond", "Crystal", "Hallowed", "Turtle",
        "Shroomite", "Chlorophyte", "Solar", "Vortex", "Nebula", "Stardust",
        "Luminite"
    };

    public static PlayerState GetCurrentState()
    {
        return new PlayerState
        {
            IsHardmode = _isHardmode,
            MoonLordDefeated = _moonLordDefeated,
            CurrentBiome = _currentBiome,
            BossesDefeated = _bossesDefeated.ToList(),
            ArmorTier = _armorTier,
            WeaponsTier = _weaponsTier,
            CurrentNPCs = _currentNPCs.ToList(),
        };
    }

    public static string GetProgressSummary()
    {
        var state = GetCurrentState();
        var lines = new List<string>
        {
            "=== Your Progress ===",
            $"Hardmode: {(state.IsHardmode ? "Yes!" : "Not yet")}",
            $"Moon Lord: {(state.MoonLordDefeated ? "Defeated!" : "Still standing")}",
            $"Bosses defeated: {state.BossesDefeated.Count}",
            $"Armor tier: {state.ArmorTier}",
            $"Weapons tier: {state.WeaponsTier}",
            $"Current biome: {state.CurrentBiome}",
        };

        if (state.BossesDefeated.Count > 0)
        {
            lines.Add($"Bosses: {string.Join(", ", state.BossesDefeated)}");
        }

        return string.Join("\n", lines);
    }

    /// <summary>
    /// Call this when any NPC is killed. Updates boss tracking.
    /// </summary>
    public static void OnNPCKilled(int npcType)
    {
        foreach (var entry in BossToNPCID)
        {
            if (entry.Value == npcType && !_bossesDefeated.Contains(entry.Key))
            {
                _bossesDefeated.Add(entry.Key);
                Terraria.Main.NewText($"[RAG] Boss tracked: {entry.Key}");
            }
        }
    }

    /// <summary>
    /// Call this when hardmode is activated (Wall of Flesh killed).
    /// </summary>
    public static void OnHardmodeActivated()
    {
        _isHardmode = true;
        Terraria.Main.NewText("[RAG] Hardmode activated! Difficulty increased!");
    }

    /// <summary>
    /// Call this to update detected biome from player position.
    /// </summary>
    public static void UpdateBiomeFromPlayer(Terraria.Player player)
    {
        // Use vanilla biome detection helpers
        if (player.ZoneSkyHeight)
            _currentBiome = "Sky";
        else if (player.ZoneOverworldHeight)
            _currentBiome = "Surface";
        else if (player.ZoneDirtLayerHeight)
            _currentBiome = "Underground";
        else if (player.ZoneRockLayerHeight)
            _currentBiome = "Cavern";
        else if (player.ZoneUnderworldHeight)
            _currentBiome = "Underworld";
        else if (player.ZoneJungle)
            _currentBiome = "Jungle";
        else if (player.ZoneCorrupt)
            _currentBiome = "Corruption";
        else if (player.ZoneCrimson)
            _currentBiome = "Crimson";
        else if (player.ZoneHallow)
            _currentBiome = "Hallow";
        else if (player.ZoneSnow)
            _currentBiome = "Snow";
        else if (player.ZoneDesert)
            _currentBiome = "Desert";
        else if (player.ZoneOcean)
            _currentBiome = "Ocean";
        else if (player.ZoneGlowshroom)
            _currentBiome = "Glowing Mushroom";
        else
            _currentBiome = "Unknown";
    }

    /// <summary>
    /// Estimate armor tier from equipped armor.
    /// </summary>
    public static void UpdateArmorTier(Terraria.Player player)
    {
        var armor = player.armor;
        var armorSet = player.setArmor;

        // Find highest tier in current armor
        // This is a simplified check — a real implementation would
        // use item.LegSlot's IDs or armor set bonuses
        var currentArmorNames = armor
            .Where(i => i.active)
            .Select(i => i.Name)
            .ToHashSet();

        string detected = "Iron";
        foreach (var tier in ArmorTierOrder)
        {
            if (currentArmorNames.Any(n => n.Contains(tier)))
            {
                detected = tier;
                break;
            }
        }

        _armorTier = detected;
    }

    // Call hooks from ModPlayer
    public static void Initialize()
    {
        // Hook into Terraria events
        // Terraria.Main.OnWorldGen += ;
        // Terraria.Main.OnSpawnNPC += ;
    }
}

public struct PlayerState
{
    public bool IsHardmode;
    public bool MoonLordDefeated;
    public string CurrentBiome;
    public List<string> BossesDefeated;
    public string ArmorTier;
    public string WeaponsTier;
    public List<string> CurrentNPCs;
}
