package routor.src.di

import android.content.Context
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import routor.src.dialogFactory.confirmDialog.ConfirmDialogFactory

@Module
@InstallIn(SingletonComponent::class)
object DialogFactoryModule {
    @Provides
    fun provideConfirmDialogFactory(@ApplicationContext context: Context): ConfirmDialogFactory {
        return ConfirmDialogFactory()
    }
}