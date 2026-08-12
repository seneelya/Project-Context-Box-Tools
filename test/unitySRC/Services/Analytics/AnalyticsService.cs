using System;
using System.Collections.Generic;
using Code.Services.Analytics.Adapters;
using Code.Services.Missions;
using Code.Services.Player;
using UnityEngine;
using VContainer;

namespace Code.Services.Analytics
{
  public class AnalyticsService : IAnalyticsService, IDisposable
  {
    [Inject] private IMissionService _missionService;
    [Inject] private IPlayerService _playerService;

    private IAnalyticsAdapter _adapter;
    private float _missionStartTime;

    public void Initialize()
    {
      _adapter = new FirebaseAnalyticsAdapter();
      _adapter.Initialize();

      SubscribeToEvents();

      LogDebug("AnalyticsService initialized");
    }
    public void Dispose()
    {
      UnsubscribeFromEvents();
    }

    private void SubscribeToEvents()
    {
      _missionService.MissionStarted += OnMissionStarted;
      _missionService.MissionCompleted += OnMissionCompleted;
      _missionService.MissionFailed += OnMissionFailed;
    }

    private void UnsubscribeFromEvents()
    {
      _missionService.MissionStarted -= OnMissionStarted;
      _missionService.MissionCompleted -= OnMissionCompleted;
      _missionService.MissionFailed -= OnMissionFailed;
    }

    private void OnMissionStarted(string missionId)
    {
      _missionStartTime = Time.time;
      TrackMissionStarted(missionId);
    }

    private void OnMissionCompleted(string missionId)
    {
      var duration = Time.time - _missionStartTime;

      if (!_playerService.MissionProgress(missionId, out var progress))
      {
        TrackMissionCompleted(missionId, duration);
        return;
      }

      TrackMissionCompleted(missionId, duration, stars: progress.Stars);
    }

    private void OnMissionFailed(string missionId)
    {
      var duration = Time.time - _missionStartTime;
      TrackMissionFailed(missionId, duration);
    }

    public void SetUserId(string userId)
    {
      _adapter.SetUserId(userId);
      // LogDebug($"User ID set: {userId}");
    }

    private void TrackMissionStarted(string missionId)
    {
      var parameters = new Dictionary<string, object>
      {
        { AnalyticsParams.MissionId, missionId }
      };

      Track(AnalyticsEvents.MissionStarted, parameters);
    }

    private void TrackMissionCompleted(string missionId, float durationSeconds, int stars = 0)
    {
      Track(AnalyticsEvents.MissionCompleted, new Dictionary<string, object>
      {
        { AnalyticsParams.MissionId, missionId },
        { AnalyticsParams.MissionDuration, (long)durationSeconds },
        { AnalyticsParams.Stars, stars }
      });
    }

    private void TrackMissionFailed(string missionId, float durationSeconds)
    {
      var parameters = new Dictionary<string, object>
      {
        { AnalyticsParams.MissionId, missionId },
        { AnalyticsParams.MissionDuration, (long)durationSeconds }
      };

      Track(AnalyticsEvents.MissionFailed, parameters);
    }

    protected void Track(string eventName, Dictionary<string, object> parameters = null)
    {
      // LogDebug(eventName, parameters);
      _adapter.Send(eventName, parameters);
    }

    private void LogDebug(string message)
    {
      Debug.Log($"[Analytics] {message}");
    }
    private void LogDebug(string eventName, Dictionary<string, object> parameters)
    {
      var paramsStr = parameters != null
        ? string.Join(", ", System.Linq.Enumerable.Select(parameters, p => $"{p.Key}={p.Value}"))
        : "none";
      Debug.Log($"[Analytics] {eventName} | {paramsStr}");
    }
  }
}
