namespace Code.Services.Analytics
{
  public interface IAnalyticsService
  {
    void Initialize();
    void SetUserId(string userId);
  }
}
