// toplevel.cs — фиктивные данные для теста .0 (C#)

using System;
using System.Collections.Generic;

namespace Orchard.Fruit;   // file-scoped namespace (без фигурных скобок)

public enum Ripeness { Green, Ripe, Rotten }

public record Apple(string Name, int Weight);

public static class Constants
{
    public const int MaxBoxes = 12;
    public static readonly string DefaultTag = "fresh";
}

[Serializable]
public class Warehouse
{
    private readonly List<Apple> _apples = new();

    public void Add(Apple a) => _apples.Add(a);

    public int Count => _apples.Count;
}
