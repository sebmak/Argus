package com.facedetection.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.models.Person
import com.facedetection.app.data.models.UnrecognizedDetection
import com.facedetection.app.ui.components.FaceEngineTopBar
import com.facedetection.app.ui.components.GlassCard
import com.facedetection.app.ui.theme.BgInput
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BgSurfaceCard
import com.facedetection.app.ui.theme.BorderSubtle
import com.facedetection.app.ui.theme.BrandAmber
import com.facedetection.app.ui.theme.BrandCyan
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Screen for reviewing unknown faces and assigning them to household members.
 */
@Composable
fun ReviewQueueScreen(
    apiClient: FaceEngineApiClient,
    onSwitchServer: () -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<UnrecognizedDetection>>(emptyList()) }
    var persons by remember { mutableStateOf<List<Person>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var selectedItemForAssignment by remember { mutableStateOf<UnrecognizedDetection?>(null) }
    var newPersonName by remember { mutableStateOf("") }

    fun loadData() {
        coroutineScope.launch {
            isLoading = true
            apiClient.getUnrecognizedDetections().onSuccess { queue ->
                items = queue
            }
            apiClient.getPersons().onSuccess { list ->
                persons = list
            }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        loadData()
    }

    val configuration = LocalConfiguration.current
    val isExpanded = configuration.screenWidthDp >= 600

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgRoot)
    ) {
        FaceEngineTopBar(
            title = "Review Queue",
            serverHost = apiClient.getBaseUrl().removePrefix("http://").removePrefix("https://"),
            isConnected = true,
            onRefresh = { loadData() },
            onServerClick = onSwitchServer
        )

        if (isLoading && items.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = BrandPrimary)
            }
        } else if (items.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        imageVector = Icons.Default.Check,
                        contentDescription = null,
                        tint = BrandEmerald,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "All Caught Up!",
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "No pending unknown face crops require assignment.",
                        color = TextMuted,
                        fontSize = 13.sp
                    )
                }
            }
        } else {
            LazyVerticalGrid(
                columns = if (isExpanded) GridCells.Adaptive(260.dp) else GridCells.Fixed(1),
                contentPadding = PaddingValues(16.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                items(items, key = { it.id }) { item ->
                    ReviewCard(
                        item = item,
                        baseUrl = apiClient.getBaseUrl(),
                        onAssign = { selectedItemForAssignment = item },
                        onIgnore = {
                            coroutineScope.launch {
                                apiClient.dismissDetection(item.id)
                                items = items.filter { it.id != item.id }
                            }
                        }
                    )
                }
            }
        }
    }

    // Assign Dialog
    selectedItemForAssignment?.let { currentItem ->
        AlertDialog(
            onDismissRequest = {
                selectedItemForAssignment = null
                newPersonName = ""
            },
            containerColor = BgSurfaceCard,
            title = {
                Text(
                    text = "Assign Face Crop",
                    color = TextPrimary,
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp
                )
            },
            text = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Choose an existing household member or create a new person.",
                        color = TextSecondary,
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    Text(
                        text = "Assign to Existing Person",
                        color = TextPrimary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height((persons.size.coerceAtMost(4) * 44).dp)
                    ) {
                        items(persons) { person ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable {
                                        coroutineScope.launch {
                                            apiClient.assignDetection(currentItem.id, person.id, null)
                                            items = items.filter { it.id != currentItem.id }
                                            selectedItemForAssignment = null
                                        }
                                    }
                                    .padding(vertical = 10.dp, horizontal = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = person.name,
                                    color = BrandCyan,
                                    fontWeight = FontWeight.Medium,
                                    fontSize = 14.sp
                                )
                                Spacer(modifier = Modifier.weight(1f))
                                Text(
                                    text = "${person.sampleCount} samples",
                                    color = TextMuted,
                                    fontSize = 11.sp
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                    Text(
                        text = "Or Create New Member",
                        color = TextPrimary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = newPersonName,
                        onValueChange = { newPersonName = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("e.g. John Doe", color = TextMuted) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = BgInput,
                            unfocusedContainerColor = BgInput,
                            focusedBorderColor = BrandPrimary,
                            unfocusedBorderColor = BorderSubtle,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        ),
                        shape = RoundedCornerShape(10.dp)
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (newPersonName.isNotBlank()) {
                            coroutineScope.launch {
                                apiClient.assignDetection(currentItem.id, null, newPersonName.trim())
                                items = items.filter { it.id != currentItem.id }
                                selectedItemForAssignment = null
                                newPersonName = ""
                            }
                        }
                    },
                    enabled = newPersonName.isNotBlank(),
                    colors = ButtonDefaults.buttonColors(containerColor = BrandPrimary)
                ) {
                    Text("Create & Assign")
                }
            },
            dismissButton = {
                TextButton(onClick = { selectedItemForAssignment = null }) {
                    Text("Cancel", color = TextMuted)
                }
            }
        )
    }
}

@Composable
private fun ReviewCard(
    item: UnrecognizedDetection,
    baseUrl: String,
    onAssign: () -> Unit,
    onIgnore: () -> Unit
) {
    val formattedTime = remember(item.timestamp) {
        if (item.timestamp > 0) {
            val date = Date((item.timestamp * 1000).toLong())
            SimpleDateFormat("MMM d, h:mm a", Locale.getDefault()).format(date)
        } else {
            "Recent"
        }
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1.2f)
                    .clip(RoundedCornerShape(12.dp))
                    .background(BgInput),
                contentAlignment = Alignment.Center
            ) {
                val fullUrl = if (!item.thumbnailUrl.isNullOrBlank()) {
                    if (item.thumbnailUrl.startsWith("http")) item.thumbnailUrl else "$baseUrl${item.thumbnailUrl}"
                } else null

                if (fullUrl != null) {
                    AsyncImage(
                        model = fullUrl,
                        contentDescription = "Unknown face crop",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                }

                // Confidence badge overlay
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(8.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .background(BrandAmber.copy(alpha = 0.9f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "Confidence: ${String.format("%.1f", item.confidence * 100)}%",
                        color = TextPrimary,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "${item.cameraId ?: "Camera"} • $formattedTime",
                color = TextSecondary,
                fontSize = 12.sp
            )

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedButton(
                    onClick = onIgnore,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Ignore",
                        tint = BrandRose,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Ignore", color = BrandRose, fontSize = 12.sp)
                }

                Button(
                    onClick = onAssign,
                    modifier = Modifier.weight(1.3f),
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = BrandPrimary,
                        contentColor = TextPrimary
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.PersonAdd,
                        contentDescription = "Assign",
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Assign", fontSize = 12.sp)
                }
            }
        }
    }
}
