import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Appearance } from 'react-native';
import { useTranslation } from 'react-i18next';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../utils/api';
import Icon from 'react-native-vector-icons/Ionicons';

const ThemeSettingsScreen = () => {
  const { t } = useTranslation();
  const [theme, setTheme] = useState('system');

  useEffect(() => {
    loadTheme();
  }, []);

  const loadTheme = async () => {
    const storedTheme = await AsyncStorage.getItem('theme_preference') || 'system';
    setTheme(storedTheme);
  };

  const handleThemeChange = async (newTheme) => {
    setTheme(newTheme);
    await AsyncStorage.setItem('theme_preference', newTheme);
    // Sync with backend
    try {
      await api.put('/user/theme', { theme: newTheme });
    } catch (error) {
      console.error('Theme sync error:', error);
    }
    // Global theme change (usually handled by a context provider at root)
    // DeviceEventEmitter.emit('themeChanged', newTheme);
  };

  const renderOption = (label, value) => (
    <TouchableOpacity
      style={styles.option}
      onPress={() => handleThemeChange(value)}
    >
      <Text style={styles.optionLabel}>{label}</Text>
      {theme === value && (
        <Icon name="checkmark" size={24} color="#007AFF" />
      )}
    </TouchableOpacity>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        {renderOption(t('follow_system'), 'system')}
        <View style={styles.separator} />
        {renderOption(t('forced_off'), 'light')}
        <View style={styles.separator} />
        {renderOption(t('forced_on'), 'dark')}
      </View>
      <Text style={styles.hint}>
        System mode will automatically switch based on your device settings.
      </Text>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  section: { backgroundColor: '#FFF', paddingHorizontal: 16, marginTop: 16 },
  option: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 16 },
  optionLabel: { fontSize: 16, color: '#333' },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: '#C7C7CC' },
  hint: { padding: 16, paddingTop: 8, fontSize: 14, color: '#8E8E93' }
});

export default ThemeSettingsScreen;
