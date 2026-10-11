import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, FlatList, Alert, Modal, TextInput } from 'react-native';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';
import Icon from 'react-native-vector-icons/Ionicons';

const AccountSecurityScreen = () => {
  const { t } = useTranslation();
  const [devices, setDevices] = useState([]);
  const [isPasswordModalVisible, setIsPasswordModalVisible] = useState(false);
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordStrength, setPasswordStrength] = useState(0);

  useEffect(() => {
    loadDevices();
  }, []);

  const loadDevices = async () => {
    try {
      const { data } = await api.get('/user/devices');
      setDevices(data);
    } catch (error) {
      console.error('Load devices error:', error);
    }
  };

  const handleLogoutDevice = async (deviceId) => {
    Alert.alert(t('logout_device'), t('confirm_logout'), [
      { text: t('cancel'), style: 'cancel' },
      { text: t('confirm'), onPress: async () => {
        try {
          await api.post('/user/logout-device', { device_id: deviceId });
          setDevices(devices.filter(d => d.device_id !== deviceId));
        } catch (error) {
          Alert.alert(t('settings'), 'Logout failed');
        }
      }}
    ]);
  };

  const checkPasswordStrength = (pwd) => {
    let score = 0;
    if (pwd.length >= 8) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[a-z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[@$!%*?&]/.test(pwd)) score++;
    setPasswordStrength(score);
  };

  const handleChangePassword = async () => {
    if (passwordStrength < 5) {
      Alert.alert(t('settings'), 'Password does not meet requirements');
      return;
    }

    try {
      await api.post('/user/change-password', { old_password: password, new_password: newPassword });
      Alert.alert(t('settings'), 'Password changed successfully, please login again');
      setIsPasswordModalVisible(false);
      // Force logout and redirect to login
    } catch (error) {
      Alert.alert(t('settings'), error.response?.data?.message || 'Change failed');
    }
  };

  const renderDevice = ({ item }) => (
    <View style={styles.deviceItem}>
      <View>
        <Text style={styles.deviceName}>{item.device_name} ({item.system_version})</Text>
        <Text style={styles.deviceIp}>IP: {item.ip_address} | {new Date(item.last_active_at).toLocaleString()}</Text>
      </View>
      <TouchableOpacity onPress={() => handleLogoutDevice(item.device_id)}>
        <Text style={styles.logoutText}>{t('logout_device')}</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.item} onPress={() => {}}>
        <Text style={styles.itemTitle}>{t('phone_email_binding')}</Text>
        <Icon name="chevron-forward" size={20} color="#C7C7CC" />
      </TouchableOpacity>

      <TouchableOpacity style={styles.item} onPress={() => setIsPasswordModalVisible(true)}>
        <Text style={styles.itemTitle}>{t('change_password')}</Text>
        <Icon name="chevron-forward" size={20} color="#C7C7CC" />
      </TouchableOpacity>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{t('login_devices')}</Text>
      </View>

      <FlatList
        data={devices}
        renderItem={renderDevice}
        keyExtractor={(item) => item.device_id}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />

      <Modal visible={isPasswordModalVisible} animationType="slide">
        <View style={styles.modalContainer}>
          <Text style={styles.modalTitle}>{t('change_password')}</Text>
          <TextInput
            style={styles.input}
            placeholder={t('password')}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
          <TextInput
            style={styles.input}
            placeholder="New Password (8-32 chars, A-Z, a-z, 0-9, special)"
            secureTextEntry
            value={newPassword}
            onChangeText={(text) => {
              setNewPassword(text);
              checkPasswordStrength(text);
            }}
          />
          <View style={styles.strengthBar}>
            {[1, 2, 3, 4, 5].map(i => (
              <View
                key={i}
                style={[
                  styles.strengthSegment,
                  { backgroundColor: i <= passwordStrength ? (passwordStrength >= 5 ? '#34C759' : '#FF9500') : '#E5E5EA' }
                ]}
              />
            ))}
          </View>
          <Text style={styles.strengthText}>{t('password_strength')}: {passwordStrength}/5</Text>

          <View style={styles.modalButtons}>
            <TouchableOpacity style={styles.button} onPress={() => setIsPasswordModalVisible(false)}>
              <Text style={styles.buttonText}>{t('cancel')}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.button, styles.primaryButton]} onPress={handleChangePassword}>
              <Text style={[styles.buttonText, { color: '#FFF' }]}>{t('confirm')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  item: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: '#FFF', marginBottom: 1 },
  itemTitle: { fontSize: 16, color: '#333' },
  sectionHeader: { padding: 16, paddingBottom: 8 },
  sectionTitle: { fontSize: 14, color: '#8E8E93', textTransform: 'uppercase' },
  deviceItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: '#FFF' },
  deviceName: { fontSize: 16, color: '#333' },
  deviceIp: { fontSize: 12, color: '#8E8E93', marginTop: 4 },
  logoutText: { color: '#FF3B30', fontSize: 14 },
  separator: { height: StyleSheet.hairlineWidth, backgroundColor: '#C7C7CC' },
  modalContainer: { flex: 1, padding: 24, justifyContent: 'center', backgroundColor: '#FFF' },
  modalTitle: { fontSize: 24, fontWeight: 'bold', marginBottom: 24, textAlign: 'center' },
  input: { borderWidth: 1, borderColor: '#E5E5EA', padding: 12, borderRadius: 8, marginBottom: 16, fontSize: 16 },
  strengthBar: { flexDirection: 'row', height: 4, marginBottom: 8 },
  strengthSegment: { flex: 1, marginHorizontal: 2, borderRadius: 2 },
  strengthText: { fontSize: 12, color: '#8E8E93', marginBottom: 24 },
  modalButtons: { flexDirection: 'row', justifyContent: 'space-between' },
  button: { flex: 1, padding: 16, borderRadius: 8, alignItems: 'center', marginHorizontal: 8, backgroundColor: '#F2F2F7' },
  primaryButton: { backgroundColor: '#007AFF' },
  buttonText: { fontSize: 16, fontWeight: '600' }
});

export default AccountSecurityScreen;
