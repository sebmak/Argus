package com.facedetection.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.facedetection.app.data.FaceEngineApiClient
import com.facedetection.app.data.models.EventLog
import com.facedetection.app.ui.components.FaceEngineTopBar
import com.facedetection.app.ui.components.GlassCard
import com.facedetection.app.ui.theme.BgInput
import com.facedetection.app.ui.theme.BgRoot
import com.facedetection.app.ui.theme.BrandAmber
import com.facedetection.app.ui.theme.BrandCyan
import com.facedetection.app.ui.theme.BrandEmerald
import com.facedetection.app.ui.theme.BrandPrimary
import com.facedetection.app.ui.theme.BrandPurple
import com.facedetection.app.ui.theme.BrandRose
import com.facedetection.app.ui.theme.TextMuted
import com.facedetection.app.ui.theme.TextPrimary
import com.facedetection.app.ui.theme.TextSecondary
import kotlinx.coroutines.launch

/**
 * Rules for EventsScreen:
 * 1. State variables and reactive properties must be declared at the top of the composable.
 * 2. Asynchronous operations and event querying must prefer Coroutines.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Displays real-time operational logs filtered by category with level severity badges.
 */
@Composable
fun EventsScreen(
    apiClient: FaceEngineApiClient,
    onSwitchServer: () -> Unit
) {
    val coroutineScope = rememberCoroutineScope()
    var events by remember { mutableStateOf<List<EventLog>>(emptyList()) }
    var selectedCategory by remember { mutableStateOf("All") }
    var isLoading by remember { mutableStateOf(true) }

    val categories = listOf("All", "detection", "motion", "system", "auth", "mqtt", "webhook", "error")

    fun loadEvents() {
        coroutineScope.launch {
            isLoading = true
            apiClient.getEvents(category = selectedCategory).onSuccess {
                events = it
            }
            isLoading = false
        }
    }

    LaunchedEffect(selectedCategory) {
        loadEvents()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgRoot)
    ) {
        FaceEngineTopBar(
            title = "System Events",
            serverHost = apiClient.getBaseUrl().removePrefix("http://").removePrefix("https://"),
            isConnected = true,
            onRefresh = { loadEvents() },
            onServerClick = onSwitchServer
        )

        // Filter chips horizontal scroll row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            categories.forEach { category ->
                val isSelected = selectedCategory == category
                FilterChip(
                    selected = isSelected,
                    onClick = { selectedCategory = category },
                    label = {
                        Text(
                            text = category.replaceFirstChar { it.uppercase() },
                            fontSize = 12.sp
                        )
                    },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = BrandPrimary,
                        selectedLabelColor = TextPrimary,
                        containerColor = BgInput,
                        labelColor = TextSecondary
                    )
                )
            }
        }

        if (isLoading && events.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = BrandPrimary)
            }
        } else if (events.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        imageVector = Icons.Default.History,
                        contentDescription = null,
                        tint = TextMuted,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(14.dp))
                    Text(
                        text = "No Events Found",
                        color = TextPrimary,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "No events logged in the '$selectedCategory' category.",
                        color = TextMuted,
                        fontSize = 12.sp
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(events, key = { "${it.id}_${it.timestamp}" }) { item ->
                    EventRowCard(item = item)
                }
            }
        }
    }
}

@Composable
private fun EventRowCard(item: EventLog) {
    val categoryColor = when (item.category.lowercase()) {
        "detection" -> BrandEmerald
        "motion" -> BrandCyan
        "system" -> BrandPurple
        "auth" -> BrandAmber
        "error" -> BrandRose
        "mqtt" -> BrandCyan
        "webhook" -> BrandAmber
        else -> BrandPrimary
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            Box(
                modifier = Modifier
                    .padding(top = 4.dp)
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(categoryColor)
            )

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(categoryColor.copy(alpha = 0.15f))
                            .padding(horizontal = 7.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = item.category.uppercase(),
                            color = categoryColor,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    Text(
                        text = item.timestamp,
                        color = TextMuted,
                        fontSize = 11.sp
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = item.message,
                    color = TextPrimary,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )

                if (item.details.isNotBlank()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = item.details,
                        color = TextSecondary,
                        fontSize = 11.sp
                    )
                }
            }
        }
    }
}
