import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, Switch, Alert, ToastAndroid, Platform, ActivityIndicator } from 'react-native';
import { useTranslation } from 'react-i18next';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DeviceInfo from 'react-native-device-info';
import api from '../utils/api';
import { getTheme } from '../styles/theme';
import { useNavigation } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/Ionicons';

const SettingsScreen = () => {
  const { t, i18n } = useTranslation();
  const navigation = useNavigation();
  const [theme, setTheme] = useState('system');
  const [lang, setLang] = useState('zh-CN');
  const [pushEnabled, setPushEnabled] = useState(true);
  const [cacheSize, setCacheSize] = useState('0.00');
  const [isLoading, setIsLoading] = useState(false);
  const [version, setVersion] = useState('1.0.0');

  useEffect(() => {
    loadSettings();
    calculateCache();
    setVersion(DeviceInfo.getVersion());
  }, []);

  const loadSettings = async () => {
    try {
      const storedTheme = await AsyncStorage.getItem('theme_preference') || 'system';
      const storedLang = await AsyncStorage.getItem('lang_preference') || 'zh-CN';
      setTheme(storedTheme);
      setLang(storedLang);

      const { data: prefs } = await api.get('/notification/preference');
      setPushEnabled(prefs.push_enabled);
    } catch (error) {
      console.error('Load settings error:', error);
    }
  };

  const calculateCache = async () => {
    // Simulated recursive file scanning logic
    // In real RN, use react-native-fs: RNFS.readDir(path), etc.
    const size = (Math.random() * 50 + 10).toFixed(2);
    setCacheSize(size);
  };

  const clearCache = async () => {
    setIsLoading(true);
    // Simulate native clearCache() API
    setTimeout(() => {
      setCacheSize('0.00');
      setIsLoading(false);
      const msg = t('cache_released', { size: cacheSize });
      if (Platform.OS === 'android') {
        ToastAndroid.show(msg, ToastAndroid.SHORT);
      } else {
        Alert.alert(t('settings'), msg);
      }
      // Trigger global event
      // DeviceEventEmitter.emit('cacheCleared');
    }, 1500);
  };

  const togglePush = async (value) => {
    try {
      const { data } = await api.put('/notification/preference', { push_enabled: value });
      if (data) setPushEnabled(value);
    } catch (error) {
      Alert.alert(t('settings'), 'Update failed, check network');
    }
  };

  const renderItem = ({ item }) => (
    <TouchableOpacity
      style={styles.item}
      onPress={item.onPress}
      disabled={item.isSwitch}
    >
      <View style={styles.itemLeft}>
        <Icon name={item.icon} size={24} color="#666" style={styles.icon} />
        <Text style={styles.itemTitle}>{item.title}</Text>
      </View>
      {item.isSwitch ? (
        <Switch
          value={item.switchValue}
          onValueChange={item.onSwitchChange}
          trackColor={{ false: "#767577", true: "#81b0ff" }}
          thumbColor={item.switchValue ? "#f5dd4b" : "#f4f3f4"}
        />
      ) : (
        <View style={styles.itemRight}>
          {item.value && <Text style={styles.itemValue}>{item.value}</Text>}
          <Icon name="chevron-forward" size={20} color="#C7C7CC" />
        </View>
      )}
    </TouchableOpacity>
  );

  const sections = [
    {
      title: t('account_security'),
      icon: 'person-outline',
      onPress: () => navigation.navigate('AccountSecurity')
    },
    {
      title: t('notifications'),
      icon: 'notifications-outline',
      onPress: () => navigation.navigate('NotificationSettings')
    },
    {
      title: t('clear_cache'),
      icon: 'trash-outline',
      value: `${cacheSize} MB`,
      onPress: () => Alert.alert(t('clear_cache'), '', [
        { text: t('cancel'), style: 'cancel' },
        { text: t('confirm'), onPress: clearCache }
      ])
    },
    {
      title: t('dark_mode'),
      icon: 'moon-outline',
      value: t(theme === 'system' ? 'follow_system' : theme === 'dark' ? 'forced_on' : 'forced_off'),
      onPress: () => navigation.navigate('ThemeSettings')
    },
    {
      title: t('language'),
      icon: 'language-outline',
      value: lang === 'zh-CN' ? '简体中文' : 'English',
      onPress: () => navigation.navigate('LanguageSettings')
    },
    {
      title: t('about_us'),
      icon: 'information-circle-outline',
      value: `v${version}`,
      onPress: () => navigation.navigate('AboutUs')
    }
  ];

  return (
    <View style={styles.container}>
      {isLoading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>{t('releasing_cache')}</Text>
        </View>
      )}
      <FlatList
        data={sections}
        renderItem={renderItem}
        keyExtractor={(item) => item.title}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    backgroundColor: '#FFFFFF',
  },
  itemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  itemRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  icon: {
    marginRight: 12,
  },
  itemTitle: {
    fontSize: 16,
    color: '#333',
  },
  itemValue: {
    fontSize: 14,
    color: '#8E8E93',
    marginRight: 8,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: '#C7C7CC',
    marginLeft: 52,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    zIndex: 1000,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#666',
  }
});

export default SettingsScreen;
