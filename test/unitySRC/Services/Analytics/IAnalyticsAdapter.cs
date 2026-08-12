using System.Collections.Generic;

namespace Code.Services.Analytics
{
  public interface IAnalyticsAdapter
  {
    void Initialize();
    void Send(string eventName, Dictionary<string, object> parameters = null);
    void SetUserProperty(string name, string value);
    void SetUserId(string userId);
  }
}
