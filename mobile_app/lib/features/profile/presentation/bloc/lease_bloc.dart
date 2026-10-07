import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_error.dart';
import '../../data/models/lease_model.dart';
import '../../data/repositories/lease_repository.dart';
import 'lease_event.dart';
import 'lease_state.dart';

/// Renting a unit out, and ending a rental.
class LeaseBloc extends Bloc<LeaseEvent, LeaseState> {
  final LeaseRepository repository;

  LeaseBloc({required this.repository}) : super(const LeaseInitialState()) {
    on<LeaseSubmitted>(_onSubmitted);
    on<LeaseEndRequested>(_onEndRequested);
    on<LeaseAdultAdded>((e, emit) => _change(emit, () => repository.addAdult(e.leaseId, e.adult)));
    on<LeaseAdultRemoved>((e, emit) => _change(emit, () => repository.removeAdult(e.leaseId, e.adultId)));
    on<LeaseDocumentAdded>((e, emit) => _change(emit, () => repository.addDocument(e.leaseId, e.document)));
    on<LeaseDocumentRemoved>((e, emit) => _change(emit, () => repository.removeDocument(e.leaseId, e.documentId)));
    on<LeaseExtended>((e, emit) => _change(emit, () => repository.extendLease(e.leaseId, e.endDate)));
    on<LeaseRenewed>(_onRenewed);
  }

  int _revision = 0;

  /// Runs one edit of a rental and reports the rental as it is afterwards.
  Future<void> _change(Emitter<LeaseState> emit, Future<LeaseModel> Function() edit) async {
    emit(const LeaseWorkingState());
    try {
      emit(LeaseChangedState(await edit(), ++_revision));
    } catch (e) {
      emit(LeaseErrorState(apiErrorMessage(e)));
    }
  }

  Future<void> _onRenewed(LeaseRenewed event, Emitter<LeaseState> emit) async {
    emit(const LeaseWorkingState());
    try {
      final lease = await repository.renewLease(
        event.leaseId,
        startDate: event.startDate,
        endDate: event.endDate,
        term: event.term,
      );
      emit(LeaseRenewedState(lease));
    } catch (e) {
      emit(LeaseErrorState(apiErrorMessage(e)));
    }
  }

  Future<void> _onSubmitted(LeaseSubmitted event, Emitter<LeaseState> emit) async {
    emit(const LeaseWorkingState());
    try {
      final lease = await repository.createLease(
        unitId: event.unitId,
        term: event.term,
        startDate: event.startDate,
        endDate: event.endDate,
        tenantName: event.tenantName,
        tenantPhone: event.tenantPhone,
        tenantNationalId: event.tenantNationalId,
        idPhotoPath: event.idPhotoPath,
        occupants: event.occupants,
      );

      // The rental exists now. Each adult and paper goes up on its own, so one
      // bad photo doesn't undo the registration — it's counted and the owner
      // is told to add it again from the rental's details.
      var failed = 0;
      var latest = lease;
      for (final adult in event.adults) {
        try {
          latest = await repository.addAdult(lease.id!, adult);
        } catch (_) {
          failed++;
        }
      }
      for (final document in event.documents) {
        try {
          latest = await repository.addDocument(lease.id!, document);
        } catch (_) {
          failed++;
        }
      }
      emit(LeaseCreatedState(latest, failedUploads: failed));
    } catch (e) {
      // The server's own reason (overlapping dates, a number that belongs to
      // someone else's account, …) rather than a raw exception string.
      emit(LeaseErrorState(apiErrorMessage(e)));
    }
  }

  Future<void> _onEndRequested(LeaseEndRequested event, Emitter<LeaseState> emit) async {
    emit(const LeaseWorkingState());
    try {
      emit(LeaseEndedState(await repository.endLease(event.leaseId)));
    } catch (e) {
      emit(LeaseErrorState(apiErrorMessage(e)));
    }
  }
}
