/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export async function bootstrapApplication({
  loadSetupState,
  playerController,
  setupController,
  setupMediaSessionHandlers,
  updateAuthUi,
  updateSetupUi,
}) {
  setupMediaSessionHandlers();
  playerController.initialize();

  updateSetupUi();
  updateAuthUi();

  await loadSetupState();

  if (setupController.isSetupAvailable()) {
    updateSetupUi();
    updateAuthUi();
  }
}
