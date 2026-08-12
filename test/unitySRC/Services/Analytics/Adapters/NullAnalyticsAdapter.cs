using System.Collections.Generic;

namespace Code.Services.Analytics.Adapters
{
  public class NullAnalyticsAdapter : IAnalyticsAdapter
  {
    public void Initialize() { }

    public void Send(string eventName, Dictionary<string, object> parameters = null) { }

    public void SetUserProperty(string name, string value) { }

    public void SetUserId(string userId) { }
  }
}
