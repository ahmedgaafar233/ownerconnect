import 'package:equatable/equatable.dart';

class ResortModel extends Equatable {
  final int id;
  final String name;
  final String? logoUrl;

  const ResortModel({required this.id, required this.name, this.logoUrl});

  factory ResortModel.fromJson(Map<String, dynamic> json) {
    return ResortModel(
      id: json['id'] as int,
      name: json['name'] as String,
      logoUrl: json['logo_url'] as String?,
    );
  }

  @override
  List<Object?> get props => [id, name, logoUrl];
}
