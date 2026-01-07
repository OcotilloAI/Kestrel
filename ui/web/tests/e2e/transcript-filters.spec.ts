import { test, expect } from '@playwright/test';
import { ensureSidebarVisible, handleLogin, ensureProjectExists } from './utils';

test('source filters hide and show messages', async ({ page }) => {
  const message = `filter-${Date.now().toString().slice(-6)}`;

  await page.goto('/');
  await handleLogin(page);
  await ensureSidebarVisible(page);

  await expect(page.getByTestId('project-select')).toBeVisible();
  await ensureProjectExists(page);

  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;
  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-main-button').click();
  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();
  await branchItem.click();

  await expect(page.getByTestId('session-status')).toHaveText(/connected/i);
  await page.getByTestId('message-input').fill(message);
  await page.getByTestId('send-button').click();
  await expect(page.getByText(message)).toBeVisible();

  await page.getByRole('button', { name: 'Filters' }).click();
  const userFilter = page.getByTestId('source-filter-user');
  await expect(userFilter).toBeVisible();
  await userFilter.click();

  await expect(page.getByText(message)).toBeHidden();
  await userFilter.click();
  await expect(page.getByText(message)).toBeVisible();
});
