import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, Modal, Platform } from 'react-native';
import { useTranslation } from 'react-i18next';
import DeviceInfo from 'react-native-device-info';
import api from '../utils/api';
import { WebView } from 'react-native-webview';
import RNFS from 'react-native-fs';
import Icon from 'react-native-vector-icons/Ionicons';

const AboutUsScreen = () => {
  const { t } = useTranslation();
  const [version, setVersion] = useState('1.0.0');
  const [policyUrl, setPolicyUrl] = useState(null);
  const [policyTitle, setPolicyTitle] = useState('');
  const [isPolicyVisible, setIsPolicyVisible] = useState(false);

  useEffect(() => {
    setVersion(DeviceInfo.getVersion());
  }, []);

  const checkUpdate = async () => {
    try {
      const { data } = await api.get('/version', {
        params: { current_version: 1, platform: Platform.OS } // using version code 1 for simulation
      });

      if (data.latest_version) {
        Alert.alert(
          'Update Available',
          `New version ${data.latest_version} is available.\n\nLog:\n${data.update_log}`,
          [
            { text: 'Later', style: 'cancel', onPress: () => { if (data.is_force_update) Alert.alert('Force Update Required'); } },
            { text: 'Update Now', onPress: () => console.log('Downloading from:', data.download_url) }
          ],
          { cancelable: !data.is_force_update }
        );
      } else {
        Alert.alert(t('settings'), 'App is up to date');
      }
    } catch (error) {
      console.error('Check update error:', error);
      Alert.alert(t('settings'), 'Update check failed');
    }
  };

  const openPolicy = async (title, url) => {
    setPolicyTitle(title);
    const offlinePath = `${RNFS.DocumentDirectoryPath}/offline/${title}.html`;

    try {
      const exists = await RNFS.exists(offlinePath);
      if (exists) {
        setPolicyUrl(`file://${offlinePath}`);
      } else {
        setPolicyUrl(url);
        // Download for offline use
        // In real app: fetch(url) then writeToFile(offlinePath)
      }
      setIsPolicyVisible(true);
    } catch (error) {
      setPolicyUrl(url);
      setIsPolicyVisible(true);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.logoContainer}>
          <Icon name="rocket" size={60} color="#007AFF" />
        </View>
        <Text style={styles.appName}>App Settings Pro</Text>
        <Text style={styles.versionText}>{t('current_version')}: v{version}</Text>
      </View>

      <View style={styles.section}>
        <TouchableOpacity style={styles.item} onPress={checkUpdate}>
          <Text style={styles.itemTitle}>{t('check_updates')}</Text>
          <Icon name="chevron-forward" size={20} color="#C7C7CC" />
        </TouchableOpacity>
        <View style={styles.separator} />
        <TouchableOpacity style={styles.item} onPress={() => openPolicy(t('user_agreement'), 'https://example.com/user-agreement')}>
          <Text style={styles.itemTitle}>{t('user_agreement')}</Text>
          <Icon name="chevron-forward" size={20} color="#C7C7CC" />
        </TouchableOpacity>
        <View style={styles.separator} />
        <TouchableOpacity style={styles.item} onPress={() => openPolicy(t('privacy_policy'), 'https://example.com/privacy-policy')}>
          <Text style={styles.itemTitle}>{t('privacy_policy')}</Text>
          <Icon name="chevron-forward" size={20} color="#C7C7CC" />
        </TouchableOpacity>
      </View>

      <Modal visible={isPolicyVisible} animationType="slide" onRequestClose={() => setIsPolicyVisible(false)}>
        <View style={styles.modalHeader}>
          <TouchableOpacity onPress={() => setIsPolicyVisible(false)}>
            <Icon name="close" size={24} color="#333" />
          </TouchableOpacity>
          <Text style={styles.modalTitle}>{policyTitle}</Text>
          <View style={{ width: 24 }} />
        </View>
        <WebView
          source={{ uri: policyUrl }}
          style={{ flex: 1 }}
          startInLoadingState={true}
          renderLoading={() => <ActivityIndicator style={{ position: 'absolute', top: '50%', left: '50%' }} />}
        />
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  header: { alignItems: 'center', paddingVertical: 40 },
  logoContainer: { width: 100, height: 100, backgroundColor: '#FFF', borderRadius: 24, justifyContent: 'center', alignItems: 'center', elevation: 4, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8 },
  appName: { fontSize: 24, fontWeight: 'bold', marginTop: 16, color: '#333' },
  versionText: { fontSize: 14, color: '#8E8E93', marginTop: 8 },
  section: { backgroundColor: '#FFF', paddingHorizontal: 16, marginTop: 16 },
  item: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 16 },
  itemTitle: { fontSize: 16, color: '#333' },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: '#C7C7CC' },
  modalHeader: { height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#C7C7CC', backgroundColor: '#FFF' },
  modalTitle: { fontSize: 17, fontWeight: '600', color: '#333' }
});

export default AboutUsScreen;
