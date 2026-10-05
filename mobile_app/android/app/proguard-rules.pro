# flutter_local_notifications: its receivers/serialisation are reached by
# reflection, so R8 must not rename or drop them in release builds.
-keep class com.dexterous.** { *; }
