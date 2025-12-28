import { test, expect } from '@playwright/test';

test('reload preserves transcript and session selection', async ({ page }) => {
  const message = `resume-${Date.now().toString().slice(-6)}`;

  await page.goto('/');
  const password = page.getByPlaceholder('Password');
  if (await password.count()) {
    await password.fill('k3str3lrocks');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForTimeout(1000);
  }

  const toggle = page.locator('[aria-label="Toggle sidebar"], .mobile-menu-btn');
  await expect(toggle.first()).toBeVisible();
  await toggle.first().click();

  await expect(page.getByTestId('project-select')).toBeVisible();
  await page.getByTestId('project-create-button').click();
  await page.waitForTimeout(1200);
  await toggle.first().click();

  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;
  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-main-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();
  await branchItem.click();

  await expect(page.getByTestId('session-status')).toHaveText(/connected/i);
  await expect(page.getByTestId('message-input')).toBeEnabled();
  await page.getByTestId('message-input').fill(message);
  await page.getByTestId('send-button').click();
  await expect(page.getByText(message)).toBeVisible();

  const activeSessionId = await page.evaluate(() => localStorage.getItem('kestrel_active_session'));
  expect(activeSessionId).toBeTruthy();
  if (activeSessionId) {
    const transcriptResponse = await page.request.get(`/session/${activeSessionId}/transcript`);
    expect(transcriptResponse.ok()).toBeTruthy();
    const transcript = await transcriptResponse.json();
    expect(Array.isArray(transcript)).toBeTruthy();
    expect(transcript.some((event: any) => String(event?.content ?? '').includes(message))).toBeTruthy();
  }

  await page.reload();
  const storedBeforeLogin = await page.evaluate(() => localStorage.getItem('kestrel_active_session'));
  expect(storedBeforeLogin).toBe(activeSessionId);
  const passwordAfter = page.getByPlaceholder('Password');
  if (await passwordAfter.count()) {
    await passwordAfter.fill('k3str3lrocks');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForTimeout(1000);
  }

  const activeSessionAfter = await page.evaluate(() => localStorage.getItem('kestrel_active_session'));
  const sessionsResponse = await page.request.get('/sessions');
  expect(sessionsResponse.ok()).toBeTruthy();
  const sessions = await sessionsResponse.json();
  expect(Array.isArray(sessions)).toBeTruthy();
  expect(sessions.some((session: any) => session?.id === activeSessionId)).toBeTruthy();
  expect(activeSessionAfter).toBe(activeSessionId);
  if (activeSessionAfter) {
    expect(sessions.some((session: any) => session?.id === activeSessionAfter)).toBeTruthy();

    const transcriptResponse = await page.request.get(`/session/${activeSessionAfter}/transcript`);
    expect(transcriptResponse.ok()).toBeTruthy();
    const transcript = await transcriptResponse.json();
    expect(Array.isArray(transcript)).toBeTruthy();
    expect(transcript.some((event: any) => String(event?.content ?? '').includes(message))).toBeTruthy();
  }

  await expect(page.getByText(message)).toBeVisible();
});
