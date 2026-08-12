using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using Code.Core.Common.Extensions;
using Code.Core.Controllers.Cameras;
using Code.Core.Controllers.Map;
using Code.Core.Controllers.Missions;
using Code.Features.Abilities;
using Code.Features.Backend.Battle;
using Code.Features.BattleGrid;
using Code.Features.BattleGrid.Nodes;
using Code.Model.Balance.Rewards;
using Code.Model.Player;
using Code.Model.Settings.Graphics;
using Code.Services.AssetManagement;
using Code.Services.Balance;
using Code.Services.Battle.AbilityManagement.Visuals;
using Code.Services.Battle.Turns;
using Code.Services.Battle.UnitCommandService;
using Code.Services.Battle.UnitManagement;
using Code.Services.Graphics;
using Code.Services.Input;
using Code.Services.Inventory;
using Code.Services.Narrative;
using Code.Services.Player;
using Code.Services.View;
using UnityEngine;
using VContainer;
using Code.Services.Missions;
using Code.Services.Rewards;
using Code.UI.Popups;
using Code.UI.Popups.MissionInfo;
using Cysharp.Threading.Tasks;
using Unity.VisualScripting;
using VContainer.Unity;
using Object = UnityEngine.Object;
using Unit = Code.Features.Units.Unit;

namespace Code.Services.Map
{
  public class MapService : IMapService
  {
    private const int MoveDelayMs = 175;
    private const string MapId = "prologue__act_01";

    public event Action<GridNode, GridNode> OnSelectMission;
    public event Action MissionsSpawned;
    public string SelectedMissionId => _selectedMissionId;
    public MissionVisualController SelectedVisual => _selectedVisual;
    public Unit PlayerUnit => _playerUnit;

    private struct MapGroupData
    {
      public SceneGroupData GroupData;
      public SceneGroupController Controller;

      public MapGroupData(SceneGroupData groupData, SceneGroupController controller)
      {
        GroupData = groupData;
        Controller = controller;
      }
    }

    [Inject] private readonly IUnitPlacementService _unitPlacement;
    [Inject] private readonly IVisualService _abilityVisual;
    [Inject] private readonly IGridFeature _gridFeature;
    [Inject] private readonly InputService _input;
    [Inject] private readonly BalanceService _balance;
    [Inject] private readonly IPlayerService _player;
    [Inject] private readonly IUnitManagementService _unitManagement;
    [Inject] private readonly IViewService _view;
    [Inject] private readonly IUnitCommandService _commands;
    [Inject] private readonly ITurnService _turnService;
    [Inject] private readonly AbilityFeature _abilityFeature;
    [Inject] private readonly IMissionService _missions;
    [Inject] private readonly IBattleFeature _battleFeature;
    [Inject] private readonly IAssetManagementService _assetManagement;
    [Inject] private readonly CameraController _camera;
    [Inject] private readonly INarrativeService _narrative;
    [Inject] private readonly GraphicsService _graphicsService;
    [Inject] private readonly IInventoryService _inventory;

    private SceneGroupRegistry _sceneRegistry;

    private Unit _playerUnit;
    private GridNode _selectedMissionNode;
    private GridNode _moveTargetNode;
    private bool _hasInteraction;

    private string _selectedMissionId;
    private List<GridNode> _missionNodes = new();
    private Dictionary<Vector2Int, MissionVisualController> _missionVisuals = new();
    private IObjectResolver _resolver;
    private MissionVisualController _selectedVisual;
    private CancellationTokenSource _cameraFollowCancellation;

    public async void Init(SceneGroupRegistry sceneRegistry)
    {
      _sceneRegistry = sceneRegistry;
      Subscribe();

      _gridFeature.Init();
      _missions.Init();

      await SpawnMissions();
      await SpawnPlayer();

      // Trigger map loaded narrative
      _narrative.ShowNarrative(NarrativeEventType.MapLoaded, MapId);

      Debug.Log($"Init MapService");
    }
    public void Dispose()
    {
      Unsubscribe();

      _moveTargetNode = null;
      _selectedVisual = null;
      _selectedMissionNode = null;
      _selectedMissionId = string.Empty;
      
      if (_camera is MenuCameraController menuCamera)
        menuCamera.StopCameraFollow();

      Debug.Log($"Dispose MapService");
    }

    private void Subscribe()
    {
      _abilityFeature.Subscribe();
      // _input.SingleTap += OnSingleTap;
      _commands.BeginAction += OnBeginAction;
      _commands.EndAction += OnEndAction;
    }

    private void Unsubscribe()
    {
      _abilityFeature.Unsubscribe();

      // _input.SingleTap -= OnSingleTap;
      _commands.BeginAction -= OnBeginAction;
      _commands.EndAction -= OnEndAction;
    }

    public void SetResolver(IObjectResolver resolver) => _resolver = resolver;
    public void SetInteraction(bool enabled)
    {
      if (enabled)
      {
        if (_camera is MenuCameraController menuCamera)
          menuCamera.SetMap();

        _graphicsService.ChangeGraphics(_camera.Settings.RenderQuality);
        _input.SingleTap += OnSingleTap;

        UpdateCameraTarget();
      }
      else
      {
        if (_camera is MenuCameraController menuCamera)
          menuCamera.SetPreview();
        _graphicsService.ChangeGraphics(_camera.Settings.RenderQuality);
        _input.SingleTap -= OnSingleTap;
      }
    }
    public List<GridNode> MissionNodes() => _missionNodes;
    public void ShowMissionVisual() => _selectedVisual?.Enable();
    public void HideMissionVisual() => _selectedVisual?.Disable();

    public async UniTask MoveToMission(bool autoStart = false)
    {
      if (_moveTargetNode == null)
        return;

      await _commands.MoveAction(_moveTargetNode);

      if (autoStart && _missions.AllowedToStart(_selectedMissionId))
        TryStartMission();
      else
        _view.ShowPopup<MissionInfoPopup, string>(_selectedMissionId);
    }

    private void OnSingleTap(Vector2 position)
    {
      if (!_gridFeature.TryClickCell(position, out var node) || !_commands.IsReady)
        return;

      var coordinate = node.Coordinates;
      if (_missions.TryGetMissionAtCoordinate(coordinate, out var missionId))
      {
        _commands.DeselectNode();
        SelectMission(missionId, node);
        return;
      }

      _commands.TryAction(node);

      DeselectMission();
    }

    private void DeselectMission()
    {
      _selectedVisual?.Disable();
      _moveTargetNode = null;
      _selectedVisual = null;
      _selectedMissionNode = null;
      _selectedMissionId = string.Empty;

      _view.ClosePopup<MissionInfoPopup>();
    }

    private void OnBeginAction(Unit unit)
    {
      _view.ClosePopup<MissionInfoPopup>();
      // _commands.DeselectUnit();

      // if (_camera is MenuCameraController menuCamera)
      // {
      //   if (!_camera.IsPositionVisible(unit.Position))
      //     menuCamera.MoveToPosition(unit.Position).Forget();
      // }
      if (_camera is MenuCameraController menuCamera)
      {
        if (!_camera.IsPositionVisible(unit.Position))
          menuCamera.StartCameraFollow(unit);
      }
    }
    private async void OnEndAction(Unit unit)
    {
      if (_camera is MenuCameraController menuCamera)
        menuCamera.StopCameraFollow();

      unit.ResetActions();
      _commands.SelectUnit(unit);
      _player.SetMapPosition(unit.Coordinates);

      if (_selectedMissionNode != null)
        await unit.Controller.SetRotationTo(_selectedMissionNode.WorldPosition);
    }

    private void TryStartMission()
    {
      if (_moveTargetNode == null)
        return;

      var unit = PlayerUnit;
      if (unit.Coordinates == _moveTargetNode.Coordinates)
      {
        if (_balance.Map.TryGetMap(_selectedMissionId, out var missionBalance) && !missionBalance.SceneName.IsNullOrEmpty())
          _battleFeature.InitBattle(_selectedMissionId);
        else
        {
          _narrative.OnNarrativeCompleted += OnNarrativeCompleted;
          // _missions.CompleteMission(_selectedMissionId, 3, new List<string>());
          _battleFeature.FastBattle(_selectedMissionId);

          // check narrative service for active narrative, after narrative shown display reward

          _missions.ApplyPendingMissionStates();
          SpawnMissions().Forget();

          var playerCoord = _player.Current.MapPosition ?? _balance.Main.Data.NewUser.StartNode;
          if (_gridFeature.TryGetNode(playerCoord, out var mapNode))
          {
            unit.Controller.SetPosition(mapNode.WorldPosition);
            unit.SetCoordinates(playerCoord);
          }

          _commands.DeselectUnit();
          _commands.SelectUnit(unit);
          // UpdateCameraTarget();

          if (_balance.Narrative.GetStory(_selectedMissionId).Count == 0)
          {
            _narrative.OnNarrativeCompleted -= OnNarrativeCompleted;
            _view.ShowPopup<MapRewardsPopup, string>(_selectedMissionId);
          }
        }
      }
    }

    private async UniTask CheckPlayerPosition()
    {
      if (_battleFeature.EndResponse == null)
        return;

      await UniTask.Delay(MoveDelayMs);

      var endResponse = _battleFeature.EndResponse;
      var config = _missions.MissionConfig(endResponse.BattleId);

      // Determine state from battle result
      var state = endResponse.IsVictory == 1 ? MissionState.Completed : MissionState.Failed;
      var stateConfig = GetState(config, state);

      if (stateConfig != null && stateConfig.MoveTo.HasValue && _gridFeature.TryGetNode(stateConfig.MoveTo.Value, out var moveToNode))
      {
        _commands.MoveAction(moveToNode).Forget();
        return;
      }


    }

    private void OnNarrativeCompleted(NarrativeEventType eventType, string missionId)
    {
      _narrative.OnNarrativeCompleted -= OnNarrativeCompleted;
      if (eventType == NarrativeEventType.MissionCompleted || eventType == NarrativeEventType.MissionStarted)
        _view.ShowPopup<MapRewardsPopup, string>(missionId);

      CheckPlayerPosition().Forget();
    }

    private async UniTask SpawnMissions()
    {
      _selectedVisual = null;
      _moveTargetNode = null;
      _selectedMissionNode = null;

      _missionNodes.Clear();

      foreach (var visual in _missionVisuals)
        Object.Destroy(visual.Value.gameObject);

      _missionVisuals.Clear();

      var activeMissions = _missions.ActiveMissions();

      var nodes = _gridFeature.Nodes();
      foreach (var node in nodes)
        node.Block();

      foreach (var mission in activeMissions)
      {
        var config = _missions.MissionConfig(mission.Id);

        if (!_gridFeature.TryGetNode(config.Coordinates, out var node))
          continue;

        if (!_missionNodes.Contains(node))
        _missionNodes.Add(node);

        // node.Block();
        Debug.Log($"{mission} Is Active");
        var state = GetState(config, mission.State);

        var visualPrefab = GetMissionVisual(mission.Id, state);
        var prefab = await _assetManagement.LoadPrefabAsync<MissionVisualController>(visualPrefab);
        var visual = _resolver.Instantiate(prefab, node.Cell.transform, false);
        _missionVisuals.TryAdd(node.Coordinates, visual);
      }

      foreach (var coord in _player.Current.OpenMapNodes)
      {
        if (!_gridFeature.TryGetNode(coord, out var node))
          continue;

        node.Unblock();
      }

      ApplyGroupVisibility();

      MissionsSpawned?.Invoke();
    }

    private string GetMissionVisual(string id, MissionStateConfig state)
    {
      if (!state.Visual.IsNullOrEmpty() && _assetManagement.IsValidAddressableKey(state.Visual))
        return state.Visual;

      var visualPath = $"MissInfo__{id}";

      return _assetManagement.IsValidAddressableKey(visualPath) ? visualPath : "MissionInfo__Base";
    }

    private async UniTask SpawnPlayer()
    {
      var startCoord = _player.Current.MapPosition ?? _balance.Main.Data.NewUser.StartNode;

      if (_gridFeature.TryGetNode(startCoord, out var node))
      {
        node.Unblock();

        var hero = _balance.Main.Data.NewUser.Heroes[0];
        _unitPlacement.SelectedUnit(hero);
        await _unitPlacement.AvatarPlace(node.WorldPosition, node.Coordinates, 0, _player.Current.Id);

        var placedUnits = _unitPlacement.PlacedUnits();
        _abilityFeature.Init(placedUnits);
        _unitManagement.Init(placedUnits);

        if (_unitManagement.TryGetUnit(node.Coordinates, out var unit))
        {
          OnEndAction(unit);
          unit.Controller.EnableBars(false);
          _playerUnit = unit;

          UpdateCameraTarget();
        }
      }

      CheckPlayerPosition().Forget();
    }

    private void UpdateCameraTarget()
    {
      if (_playerUnit == null)
        return;

      _camera.SetPosition(_playerUnit.Position);
    }

    private void SelectMission(string missionId, GridNode node)
    {
      if (_selectedMissionNode == node)
      {
        MoveToMission().Forget();
        return;
      }

      DeselectMission();

      _selectedMissionNode = node;
      _selectedMissionId = missionId;
      var config = _missions.MissionConfig(missionId);

      if (_missionVisuals.TryGetValue(node.Coordinates, out var visual))
      {
        _selectedVisual?.Disable();
        _selectedVisual = visual;
        _selectedVisual.Enable();
      }

      var selectedUnit = _commands.SelectedUnit;
      var maxRange = _balance.Main.TryGetAbility(selectedUnit.MoveAbility, out var ability) ? ability.Range : -1;
      // var reachable = _gridFeature.Reachable(selectedUnit.Coordinates, 1, selectedUnit.ClimbHeight);
      var neighbours = _gridFeature.Neighbours(node);
      var missionInRange = _gridFeature.TryGetNode(selectedUnit.Coordinates, out var unitNode) &&
        neighbours.Contains(unitNode) && config.ClimbHeight >= node.GetHeightDistance(unitNode);

      if (missionInRange || node.Coordinates == selectedUnit.Coordinates)
      {
        Debug.Log($"{node.Position} Is Reachable");

        _moveTargetNode = unitNode;

        OnSelectMission?.Invoke(node, _moveTargetNode);
        return;
      }

      var path = _gridFeature.FindPath(selectedUnit.Coordinates, node.Coordinates, maxRange, config.ClimbHeight, config.ClimbHeight, true);

      if (path.Count == 0)
        return;

      _moveTargetNode = path.Last();

      OnSelectMission?.Invoke(node, _moveTargetNode);
    }

    private MissionStateConfig GetState(MissionConfig config, MissionState state)
    {
      MissionStateConfig stateConfig = null;

      switch (state)
      {
        case MissionState.Spawned:
          Debug.Log($"{config.MissionId} Is Spawned");
          stateConfig = config.OnSpawn;
          break;
        case MissionState.Failed:
          Debug.Log($"{config.MissionId} Is Failed");
          stateConfig = config.OnFailed;
          break;
        case MissionState.Completed:
          Debug.Log($"{config.MissionId} Is Completed");
          stateConfig = config.OnComplete;
          break;
      }

      return stateConfig ?? new MissionStateConfig();
    }

    private void ApplyGroupVisibility()
    {
      var mapGroups = _player.Current.MapGroups;

      var fogGroups = new List<MapGroupData>();
      var mistGroups = new List<MapGroupData>();
      var otherGroups = new List<MapGroupData>();

      foreach (var groupData in mapGroups)
      {
        if (!_sceneRegistry.TryGetGroup(groupData.Id, out var group))
          continue;

        var data = new MapGroupData(groupData, group);

        if (group.GroupType == SceneGroupType.Fog)
          fogGroups.Add(data);
        else if (group.GroupType == SceneGroupType.Mist)
          mistGroups.Add(data);
        else
          otherGroups.Add(data);
      }

      foreach (var data in fogGroups)
      {
        data.Controller.SetActive(data.GroupData.IsActive, data.GroupData.IsAnimate);
        data.GroupData.IsAnimate = false;
      }

      _sceneRegistry.SyncMistToFog();

      foreach (var data in mistGroups)
      {
        data.Controller.SetActive(data.GroupData.IsActive, data.GroupData.IsAnimate);
        data.GroupData.IsAnimate = false;
      }

      foreach (var data in otherGroups)
      {
        data.Controller.SetActive(data.GroupData.IsActive, data.GroupData.IsAnimate);
        data.GroupData.IsAnimate = false;
      }

      _player.Save();
    }

    // private void StartCameraFollow(Unit unit)
    // {
    //   // Cancel any existing follow task
    //   StopCameraFollow();
    //
    //   // Create new cancellation token
    //   _cameraFollowCancellation = new CancellationTokenSource();
    //
    //   // Start following the unit
    //   FollowUnitAsync(unit, _cameraFollowCancellation.Token).Forget();
    // }
    //
    // private void StopCameraFollow()
    // {
    //   _cameraFollowCancellation?.Cancel();
    //   _cameraFollowCancellation?.Dispose();
    //   _cameraFollowCancellation = null;
    // }
    //
    // private async UniTask FollowUnitAsync(Unit unit, CancellationToken cancellationToken)
    // {
    //   try
    //   {
    //     Vector3 currentTargetPos = _camera.MovePivot.position; // MovePivot position
    //     const float arrivalThreshold = 0.1f; // Distance to consider camera has reached target
    //     bool isFollowing = false; // Track if we've started following
    //
    //     while (!cancellationToken.IsCancellationRequested)
    //     {
    //       if (unit != null && _camera != null)
    //       {
    //         var unitPos = unit.Position;
    //         var distanceToTarget = Vector3.Distance(currentTargetPos, unitPos);
    //
    //         // Check if unit position is outside camera view
    //         bool isOutsideView = !_camera.IsPositionVisible(unitPos);
    //
    //         // Start following if unit goes outside view
    //         if (isOutsideView)
    //         {
    //           isFollowing = true;
    //         }
    //
    //         // Continue moving if following and haven't reached target yet
    //         if (isFollowing && distanceToTarget > arrivalThreshold)
    //         {
    //           // Smoothly move camera towards the unit position
    //           var moveSpeed = 15f; // Adjust speed as needed for smooth following
    //
    //           // Interpolate towards the target position
    //           currentTargetPos = Vector3.MoveTowards(currentTargetPos, unitPos, moveSpeed * Time.deltaTime);
    //
    //           // Move camera to the interpolated position
    //           _camera.MoveOnTarget(currentTargetPos);
    //         }
    //         else if (distanceToTarget <= arrivalThreshold)
    //         {
    //           // Stop following when reached target
    //           isFollowing = false;
    //           currentTargetPos = _camera.MovePivot.position;
    //         }
    //       }
    //
    //       // Update every frame for smooth following
    //       await UniTask.Yield(cancellationToken);
    //     }
    //   }
    //   catch (OperationCanceledException)
    //   {
    //     // Expected when cancellation is requested
    //   }
    // }


  }
}
