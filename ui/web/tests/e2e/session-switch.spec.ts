import { test, expect } from '@playwright/test';
import { ensureSidebarVisible, handleLogin, ensureProjectExists } from './utils';

test('switching to a new branch avoids reconnecting the old session', async ({ page }) => {
  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;
  const sockets: string[] = [];

  page.on('websocket', (ws) => {
    sockets.push(ws.url());
  });

  await page.goto('/');
  await handleLogin(page);
  await ensureSidebarVisible(page);

  await expect(page.getByTestId('project-select')).toBeVisible();
  await ensureProjectExists(page);

  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-main-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();
  await branchItem.click();

  await expect(branchItem).toHaveClass(/active/);

  await page.waitForTimeout(4000);
  expect(sockets.length).toBeLessThanOrEqual(3);
});
