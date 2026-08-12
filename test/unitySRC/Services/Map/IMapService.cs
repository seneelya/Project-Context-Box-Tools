using System;
using System.Collections.Generic;
using Code.Core.Controllers.Map;
using Code.Core.Controllers.Missions;
using Code.Features.BattleGrid.Nodes;
using Code.Features.Units;
using Cysharp.Threading.Tasks;
using UnityEngine;
using VContainer;

namespace Code.Services.Map
{
  public interface IMapService : IDisposable
  {
    event Action<GridNode, GridNode> OnSelectMission;
    event Action MissionsSpawned;

    string SelectedMissionId { get; }
    Unit PlayerUnit { get; }
    void Init(SceneGroupRegistry groupRegistry);

    void SetResolver(IObjectResolver resolver);
    void SetInteraction(bool enabled);

    UniTask MoveToMission(bool autoStart = false);
    List<GridNode> MissionNodes();
    void ShowMissionVisual();
    void HideMissionVisual();
  }
}
