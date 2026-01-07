import { test, expect } from '@playwright/test';
import { ensureSidebarVisible, handleLogin, ensureProjectExists } from './utils';

test('merge branch into main from sidebar', async ({ page }) => {
  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;

  await page.goto('/');
  await handleLogin(page);
  await ensureSidebarVisible(page);

  await expect(page.getByTestId('project-select')).toBeVisible();
  await ensureProjectExists(page);

  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-main-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();

  await page.getByTestId(`branch-merge-${branchName}`).click();
  await expect(page.getByTestId('confirm-modal')).toBeVisible();
  await page.getByTestId('confirm-delete').click();

  await expect(page.getByTestId(`branch-merge-${branchName}`)).toBeVisible();
});
