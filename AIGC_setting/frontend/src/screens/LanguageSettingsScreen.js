import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { useTranslation } from 'react-i18next';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../utils/api';
import Icon from 'react-native-vector-icons/Ionicons';

const LanguageSettingsScreen = () => {
  const { t, i18n } = useTranslation();
  const [lang, setLang] = useState('zh-CN');

  useEffect(() => {
    loadLang();
  }, []);

  const loadLang = async () => {
    const storedLang = await AsyncStorage.getItem('lang_preference') || 'zh-CN';
    setLang(storedLang);
  };

  const handleLangChange = async (newLang) => {
    setLang(newLang);
    i18n.changeLanguage(newLang);
    await AsyncStorage.setItem('lang_preference', newLang);
    // Sync with backend
    try {
      await api.put('/user/language', { language: newLang });
    } catch (error) {
      console.error('Language sync error:', error);
    }
  };

  const renderOption = (label, value) => (
    <TouchableOpacity
      style={styles.option}
      onPress={() => handleLangChange(value)}
    >
      <Text style={styles.optionLabel}>{label}</Text>
      {lang === value && (
        <Icon name="checkmark" size={24} color="#007AFF" />
      )}
    </TouchableOpacity>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        {renderOption('简体中文', 'zh-CN')}
        <View style={styles.separator} />
        {renderOption('English', 'en-US')}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  section: { backgroundColor: '#FFF', paddingHorizontal: 16, marginTop: 16 },
  option: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 16 },
  optionLabel: { fontSize: 16, color: '#333' },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: '#C7C7CC' }
});

export default LanguageSettingsScreen;
