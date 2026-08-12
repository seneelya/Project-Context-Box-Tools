using System;
using System.Collections.Generic;
using UnityEngine;

namespace Code.Services.Analytics.Adapters
{
  public class CompositeAnalyticsAdapter : IAnalyticsAdapter
  {
    private readonly IReadOnlyList<IAnalyticsAdapter> _adapters;

    public CompositeAnalyticsAdapter(IReadOnlyList<IAnalyticsAdapter> adapters)
    {
      _adapters = adapters;
    }

    public void Initialize()
    {
      foreach (var adapter in _adapters)
      {
        TryExecute(adapter, a => a.Initialize());
      }
    }

    public void Send(string eventName, Dictionary<string, object> parameters = null)
    {
      foreach (var adapter in _adapters)
      {
        TryExecute(adapter, a => a.Send(eventName, parameters));
      }
    }

    public void SetUserProperty(string name, string value)
    {
      foreach (var adapter in _adapters)
      {
        TryExecute(adapter, a => a.SetUserProperty(name, value));
      }
    }

    public void SetUserId(string userId)
    {
      foreach (var adapter in _adapters)
      {
        TryExecute(adapter, a => a.SetUserId(userId));
      }
    }

    private void TryExecute(IAnalyticsAdapter adapter, Action<IAnalyticsAdapter> action)
    {
      try
      {
        action(adapter);
      }
      catch (Exception e)
      {
        Debug.LogWarning($"[Analytics] {adapter.GetType().Name} failed: {e.Message}");
      }
    }
  }
}
