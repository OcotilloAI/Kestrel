import { test, expect } from '@playwright/test';
import { ensureSidebarVisible, handleLogin } from './utils';

test('deleting an active branch removes it from the list', async ({ page }) => {
  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;

  await page.goto('/');
  await handleLogin(page);
  await ensureSidebarVisible(page);

  await expect(page.getByTestId('project-select')).toBeVisible();

  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();

  await branchItem.click();
  await expect(branchItem).toHaveClass(/active/);

  await page.getByTestId(`branch-delete-${branchName}`).click();
  await expect(page.getByTestId('confirm-modal')).toBeVisible();
  await page.getByTestId('confirm-delete').click();
  await expect(branchItem).toBeHidden();
});
