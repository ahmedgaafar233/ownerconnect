import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({Key? key}) : super(key: key);

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _fullnameController = TextEditingController();
  Map<String, dynamic>? _profile;
  bool _isLoading = true;
  bool _isSaving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _fullnameController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final profile = await context.read<AuthBloc>().repository.fetchAndPersistProfile();
      setState(() {
        _profile = profile;
        _fullnameController.text = profile['fullname'] as String? ?? '';
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() => _isSaving = true);
    try {
      final profile = await context.read<AuthBloc>().repository.updateFullname(_fullnameController.text.trim());
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _isSaving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).translate('profile_saved'))),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString()), backgroundColor: AppColors.error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('profile_title'))),
      body: _isLoading
          ? const Center(child: AppLoadingIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(loc.translate('phone_hint'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    Text(_profile?['phone'] as String? ?? '', style: const TextStyle(fontSize: 16)),
                    const SizedBox(height: 16),
                    Text(loc.translate('role_label'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    Text(
                      loc.translate((_profile?['role'] as String?) == 'TENANT' ? 'role_tenant' : 'role_owner'),
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 16),
                    Text(loc.translate('village_label'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    Text(_profile?['resort_name'] as String? ?? '-', style: const TextStyle(fontSize: 16)),
                    const SizedBox(height: 24),
                    TextField(
                      controller: _fullnameController,
                      decoration: InputDecoration(labelText: loc.translate('fullname_hint')),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: _isSaving ? null : _save,
                      child: _isSaving
                          ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                          : Text(loc.translate('save_button')),
                    ),
                  ],
                ),
    );
  }
}
