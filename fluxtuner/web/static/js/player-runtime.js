/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createPlayerRuntime() {
  let controller = null;

  function attach(nextController) {
    controller = nextController;
    return controller;
  }

  function debugSnapshot(details = {}) {
    return controller?.debugSnapshot(details) || { details };
  }

  function getCurrentStation() {
    return controller?.getCurrentStation() || null;
  }

  function initialize() {
    return controller?.initialize();
  }

  function pauseCurrentStationPlayback(message) {
    return controller?.pauseCurrentStationPlayback(message);
  }

  function playStation(station) {
    return controller?.playStation(station);
  }

  function setPlayerState(...args) {
    return controller?.setPlayerState(...args);
  }

  function startCurrentStationPlayback(message) {
    return controller?.startCurrentStationPlayback(message);
  }

  function stopPlayback(...args) {
    return controller?.stopPlayback(...args);
  }

  return {
    attach,
    debugSnapshot,
    getCurrentStation,
    initialize,
    pauseCurrentStationPlayback,
    playStation,
    setPlayerState,
    startCurrentStationPlayback,
    stopPlayback,
  };
}
