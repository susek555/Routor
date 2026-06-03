package routor.src.network

import kotlinx.serialization.Serializable

//TODO adjust structure

@Serializable
data class MyNotification(
    val event: String,
    val status: String,
    val user_ip: String,
    val message: String
)
