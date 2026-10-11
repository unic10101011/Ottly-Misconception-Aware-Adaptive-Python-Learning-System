import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Switch, ScrollView, Alert } from 'react-native';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';

const NotificationSettingsScreen = () => {
  const { t } = useTranslation();
  const [prefs, setPrefs] = useState({
    push_enabled: true,
    system_msg_enabled: true,
    activity_msg_enabled: true,
    ai_reply_enabled: true
  });

  useEffect(() => {
    loadPrefs();
  }, []);

  const loadPrefs = async () => {
    try {
      const { data } = await api.get('/notification/preference');
      setPrefs(data);
    } catch (error) {
      console.error('Load prefs error:', error);
    }
  };

  const updatePref = async (key, value) => {
    const newPrefs = { ...prefs, [key]: value };
    try {
      const { data } = await api.put('/notification/preference', newPrefs);
      if (data) setPrefs(newPrefs);
    } catch (error) {
      Alert.alert(t('settings'), 'Sync failed, check network');
    }
  };

  const renderSwitchItem = (title, key, disabled = false) => (
    <View style={[styles.item, disabled && styles.disabledItem]}>
      <Text style={styles.itemTitle}>{title}</Text>
      <Switch
        value={prefs[key]}
        onValueChange={(val) => updatePref(key, val)}
        disabled={disabled}
        trackColor={{ false: "#767577", true: "#34C759" }}
        thumbColor="#FFF"
      />
    </View>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        {renderSwitchItem(t('notifications'), 'push_enabled')}
        <Text style={styles.hint}>Receive push notifications for updates and messages.</Text>
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Preferences</Text>
      </View>

      <View style={styles.section}>
        {renderSwitchItem(t('system_notifications'), 'system_msg_enabled', !prefs.push_enabled)}
        <View style={styles.separator} />
        {renderSwitchItem(t('activity_notifications'), 'activity_msg_enabled', !prefs.push_enabled)}
        <View style={styles.separator} />
        {renderSwitchItem(t('ai_reply_notifications'), 'ai_reply_enabled', !prefs.push_enabled)}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  section: { backgroundColor: '#FFF', paddingHorizontal: 16 },
  sectionHeader: { padding: 16, paddingBottom: 8 },
  sectionTitle: { fontSize: 14, color: '#8E8E93', textTransform: 'uppercase' },
  item: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12 },
  itemTitle: { fontSize: 16, color: '#333' },
  disabledItem: { opacity: 0.5 },
  hint: { padding: 16, paddingTop: 8, fontSize: 13, color: '#8E8E93' },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: '#C7C7CC' }
});

export default NotificationSettingsScreen;
