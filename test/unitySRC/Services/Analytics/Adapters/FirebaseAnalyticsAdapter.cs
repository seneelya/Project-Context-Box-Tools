using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Cysharp.Threading.Tasks;
using Firebase;
using Firebase.Analytics;
using Firebase.Crashlytics;
using UnityEngine;

namespace Code.Services.Analytics.Adapters
{
  public class FirebaseAnalyticsAdapter : IAnalyticsAdapter
  {
    private bool _isInitialized;

    public void Initialize()
    {
      InitializeAsync().Forget();
    }

    private async UniTaskVoid InitializeAsync()
    {
      try
      {
        var dependencyStatus = await FirebaseApp.CheckAndFixDependenciesAsync();

        if (dependencyStatus == DependencyStatus.Available)
        {
          InitializeFirebaseServices();
          _isInitialized = true;
          Debug.Log("[Firebase] Initialized successfully");
        }
        else
        {
          Debug.LogError($"[Firebase] Could not resolve dependencies: {dependencyStatus}");
        }
      }
      catch (Exception e)
      {
        Debug.LogError($"[Firebase] Initialization failed: {e.Message}");
      }
    }

    private void InitializeFirebaseServices()
    {
      var app = FirebaseApp.DefaultInstance;

      Crashlytics.IsCrashlyticsCollectionEnabled = true;
      Crashlytics.ReportUncaughtExceptionsAsFatal = true;

      FirebaseAnalytics.SetAnalyticsCollectionEnabled(true);
    }

    public void Send(string eventName, Dictionary<string, object> parameters = null)
    {
      if (!_isInitialized)
        return;

      try
      {
        if (parameters == null || parameters.Count == 0)
        {
          FirebaseAnalytics.LogEvent(eventName);
        }
        else
        {
          var firebaseParams = ConvertParameters(parameters);
          FirebaseAnalytics.LogEvent(eventName, firebaseParams);
        }
      }
      catch (Exception e)
      {
        Debug.LogWarning($"[Firebase] Failed to send event '{eventName}': {e.Message}");
      }
    }

    public void SetUserProperty(string name, string value)
    {
      if (!_isInitialized)
        return;

      try
      {
        FirebaseAnalytics.SetUserProperty(name, value);
      }
      catch (Exception e)
      {
        Debug.LogWarning($"[Firebase] Failed to set user property '{name}': {e.Message}");
      }
    }

    public void SetUserId(string userId)
    {
      if (!_isInitialized)
        return;

      try
      {
        FirebaseAnalytics.SetUserId(userId);
        Crashlytics.SetUserId(userId);
      }
      catch (Exception e)
      {
        Debug.LogWarning($"[Firebase] Failed to set user ID: {e.Message}");
      }
    }

    private Parameter[] ConvertParameters(Dictionary<string, object> parameters)
    {
      return parameters.Select(p => CreateParameter(p.Key, p.Value)).ToArray();
    }

    private Parameter CreateParameter(string key, object value)
    {
      return value switch
      {
        int intValue => new Parameter(key, intValue),
        long longValue => new Parameter(key, longValue),
        float floatValue => new Parameter(key, floatValue),
        double doubleValue => new Parameter(key, doubleValue),
        string stringValue => new Parameter(key, stringValue),
        _ => new Parameter(key, value?.ToString() ?? string.Empty)
      };
    }
  }
}
