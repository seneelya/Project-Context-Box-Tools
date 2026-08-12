namespace Code.Services.Analytics
{
  public static class AnalyticsEvents
  {
    public const string MissionStarted = "mission_started";
    public const string MissionCompleted = "mission_completed";
    public const string MissionFailed = "mission_failed";
  }

  public static class AnalyticsParams
  {
    public const string MissionId = "mission_id";
    public const string MissionDuration = "mission_duration_seconds";
    public const string Stars = "stars";
  }
}
