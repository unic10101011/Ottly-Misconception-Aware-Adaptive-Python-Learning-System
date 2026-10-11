export const lightTheme = {
  '--color-bg': '#FFFFFF',
  '--color-text': '#333333',
  '--color-subtext': '#999999',
  '--color-primary': '#007AFF',
  '--color-secondary': '#F2F2F7',
  '--color-border': '#E5E5EA',
  '--color-danger': '#FF3B30',
  '--color-success': '#34C759',
  '--color-card': '#FFFFFF',
};

export const darkTheme = {
  '--color-bg': '#1C1C1E',
  '--color-text': '#FFFFFF',
  '--color-subtext': '#8E8E93',
  '--color-primary': '#0A84FF',
  '--color-secondary': '#2C2C2E',
  '--color-border': '#38383A',
  '--color-danger': '#FF453A',
  '--color-success': '#32D74B',
  '--color-card': '#2C2C2E',
};

export const getTheme = (preference, systemScheme) => {
  if (preference === 'system') {
    return systemScheme === 'dark' ? darkTheme : lightTheme;
  }
  return preference === 'dark' ? darkTheme : lightTheme;
};
