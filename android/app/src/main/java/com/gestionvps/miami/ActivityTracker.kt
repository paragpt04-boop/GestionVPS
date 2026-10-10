package com.gestionvps.miami

import org.json.JSONObject

/** Traffic evidence lasts 45 seconds; handshakes use the server's 180-second estimate. */
internal class ActivityTracker {
    private data class Sample(val total:Long,val seen:Long)
    private val samples=mutableMapOf<String,Sample>()
    fun clear()=samples.clear()
    fun annotate(data:JSONObject,now:Long):JSONObject {
        val clients=arrayObjects(data.optJSONArray("clients"))
        val ids=clients.map { it.getString("id") }.toSet()
        samples.keys.retainAll(ids)
        clients.forEach { client ->
            val id=client.getString("id")
            val total=client.optLong("received_bytes")+client.optLong("sent_bytes")
            val previous=samples[id]
            val seen=if(previous!=null&&total>previous.total) now else previous?.seen ?: 0L
            samples[id]=Sample(total,seen)
            client.put("activity_recent",!client.optBoolean("suspended") &&
                (client.optBoolean("active_estimated") || (seen>0 && now-seen<45_000)))
        }
        return data.put("observed_at_ms",now)
    }
}
