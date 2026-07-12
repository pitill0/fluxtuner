/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createPlayerRuntime() {
  let controller = null;

  function attach(nextController) {
    if (!nextController || typeof nextController !== "object") {
      throw new TypeError("Player runtime requires a controller object.");
    }

    if (controller) {
      throw new Error("Player runtime controller is already attached.");
    }

    controller = nextController;
    return controller;
  }

  function requireController() {
    if (!controller) {
      throw new Error("Player runtime controller is not attached.");
    }

    return controller;
  }

  function debugSnapshot(details = {}) {
    return controller?.debugSnapshot(details) || { details };
  }

  function getCurrentStation() {
    return controller?.getCurrentStation() || null;
  }

  function pauseCurrentStationPlayback(message) {
    return requireController().pauseCurrentStationPlayback(message);
  }

  function playStation(station) {
    return requireController().playStation(station);
  }

  function setPlayerState(...args) {
    return requireController().setPlayerState(...args);
  }

  function startCurrentStationPlayback(message) {
    return requireController().startCurrentStationPlayback(message);
  }

  function stopPlayback(...args) {
    return requireController().stopPlayback(...args);
  }

  return {
    attach,
    debugSnapshot,
    getCurrentStation,
    pauseCurrentStationPlayback,
    playStation,
    setPlayerState,
    startCurrentStationPlayback,
    stopPlayback,
  };
}
