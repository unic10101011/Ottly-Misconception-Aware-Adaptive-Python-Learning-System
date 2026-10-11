import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { Appearance, useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ThemeProvider } from 'styled-components/native';
import { getTheme } from './src/styles/theme';
import { loadLanguage } from './src/i18n';
import SettingsScreen from './src/screens/SettingsScreen';
import AccountSecurityScreen from './src/screens/AccountSecurityScreen';
import NotificationSettingsScreen from './src/screens/NotificationSettingsScreen';
import ThemeSettingsScreen from './src/screens/ThemeSettingsScreen';
import LanguageSettingsScreen from './src/screens/LanguageSettingsScreen';
import AboutUsScreen from './src/screens/AboutUsScreen';

const Stack = createStackNavigator();

const App = () => {
  const systemScheme = useColorScheme();
  const [themePreference, setThemePreference] = useState('system');

  useEffect(() => {
    const init = async () => {
      await loadLanguage();
      const storedTheme = await AsyncStorage.getItem('theme_preference') || 'system';
      setThemePreference(storedTheme);
    };
    init();

    // Listen for theme change events
    // In real app: use a global state manager (Redux/MobX/Context)
  }, []);

  const currentTheme = getTheme(themePreference, systemScheme);

  return (
    <ThemeProvider theme={currentTheme}>
      <NavigationContainer>
        <Stack.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: currentTheme['--color-bg'] },
            headerTintColor: currentTheme['--color-text'],
            cardStyle: { backgroundColor: currentTheme['--color-bg'] }
          }}
        >
          <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: 'Settings' }} />
          <Stack.Screen name="AccountSecurity" component={AccountSecurityScreen} options={{ title: 'Account & Security' }} />
          <Stack.Screen name="NotificationSettings" component={NotificationSettingsScreen} options={{ title: 'Notifications' }} />
          <Stack.Screen name="ThemeSettings" component={ThemeSettingsScreen} options={{ title: 'Dark Mode' }} />
          <Stack.Screen name="LanguageSettings" component={LanguageSettingsScreen} options={{ title: 'Language' }} />
          <Stack.Screen name="AboutUs" component={AboutUsScreen} options={{ title: 'About Us' }} />
        </Stack.Navigator>
      </NavigationContainer>
    </ThemeProvider>
  );
};

export default App;
