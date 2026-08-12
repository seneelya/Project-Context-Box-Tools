using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace Code.Services.Input
{
  public class InputService
  {
    public event Action<Vector2> SingleTap;
    public event Action<Vector2> PrimaryTapPressed;
    public event Action<Vector2> PrimaryTapReleased;
    public event Action<Vector2> SecondaryTapPressed;
    public event Action<Vector2> SecondaryTapReleased;
    public event Action<Vector2> Scroll;
    public event Action ForwardClicked;
    public event Action BackClicked;

    private InputContext _inputContext;

    public void Initialize()
    {
      _inputContext = new InputContext();

      _inputContext.Enable();
      _inputContext.PlayerInput.PrimaryTap.started += OnPrimaryTapPressed;
      _inputContext.PlayerInput.PrimaryTap.canceled += OnPrimaryTapReleased;
      _inputContext.PlayerInput.SecondaryTap.started += OnSecondaryTapPressed;
      _inputContext.PlayerInput.SecondaryTap.canceled += OnSecondaryTapReleased;
      _inputContext.PlayerInput.SingleTap.performed += OnSingleTap;
      _inputContext.UI.ScrollWheel.performed += OnScroll;
      _inputContext.PlayerInput.ForwardClick.performed += OnForwardClicked;
      _inputContext.PlayerInput.BackwardClick.performed += OnBackFlicked;
    }

    private void OnBackFlicked(InputAction.CallbackContext context) => BackClicked?.Invoke();
    private void OnForwardClicked(InputAction.CallbackContext context) => ForwardClicked?.Invoke();

    private void OnScroll(InputAction.CallbackContext context) => Scroll?.Invoke(context.ReadValue<Vector2>());

    public InputActionPhase GetPrimaryTapPhase() => _inputContext.PlayerInput.PrimaryTap.phase;

    public Vector2 GetPrimaryTapPosition() => _inputContext.PlayerInput.PrimaryTapPosition.ReadValue<Vector2>();

    public Vector2 GetPrimaryTapDelta() => _inputContext.PlayerInput.PrimaryTapDelta.ReadValue<Vector2>();

    public Vector2 GetSecondaryTapPosition() => _inputContext.PlayerInput.SecondaryTapPosition.ReadValue<Vector2>();

    public Vector2 GetSecondaryTapDelta() => _inputContext.PlayerInput.SecondaryTapDelta.ReadValue<Vector2>();

    private void OnSingleTap(InputAction.CallbackContext context) => SingleTap?.Invoke(GetPrimaryTapPosition());

    private void OnPrimaryTapPressed(InputAction.CallbackContext context) => PrimaryTapPressed?.Invoke(GetPrimaryTapPosition());

    private void OnPrimaryTapReleased(InputAction.CallbackContext context) => PrimaryTapReleased?.Invoke(GetPrimaryTapPosition());

    private void OnSecondaryTapPressed(InputAction.CallbackContext context) =>
      SecondaryTapPressed?.Invoke(GetSecondaryTapPosition());

    private void OnSecondaryTapReleased(InputAction.CallbackContext context) =>
      SecondaryTapReleased?.Invoke(GetSecondaryTapPosition());
  }
}
