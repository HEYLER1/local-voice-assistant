package com.heyler.voicelab

import android.content.Context
import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

data class ConversationEntry(val id:Long,val title:String,val updated:Long,val fragments:Int=0,val questions:Int=0,val folderId:Long?=null)
data class ConversationFolder(val id:Long,val name:String)

/** Local history is partitioned by the authenticated account. Legacy data remains separately owned until the user imports it. */
class ConversationStore(context:Context,databaseName:String="conversations.db",private val ownerId:String="legacy"):SQLiteOpenHelper(context,databaseName,null,3){
    override fun onConfigure(db:SQLiteDatabase){db.setForeignKeyConstraintsEnabled(true)}
    override fun onCreate(db:SQLiteDatabase){
        db.execSQL("CREATE TABLE folders(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE,owner_id TEXT NOT NULL,UNIQUE(owner_id,name))")
        db.execSQL("CREATE TABLE sessions(id INTEGER PRIMARY KEY,title TEXT NOT NULL,updated INTEGER NOT NULL,data TEXT NOT NULL,fragments INTEGER NOT NULL DEFAULT 0,questions INTEGER NOT NULL DEFAULT 0,folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,owner_id TEXT NOT NULL)")
        db.execSQL("CREATE INDEX sessions_folder ON sessions(owner_id,folder_id)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int){
        if(oldVersion<2){
            db.execSQL("CREATE TABLE folders(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE UNIQUE)")
            db.execSQL("ALTER TABLE sessions ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL")
            db.execSQL("CREATE INDEX sessions_folder ON sessions(folder_id)")
            db.execSQL("ALTER TABLE sessions ADD COLUMN fragments INTEGER NOT NULL DEFAULT 0")
            db.execSQL("ALTER TABLE sessions ADD COLUMN questions INTEGER NOT NULL DEFAULT 0")
            val counts=db.rawQuery("SELECT id,data FROM sessions",null).use{c->buildList{while(c.moveToNext()){val value=JSONObject(c.getString(1));add(Triple(c.getLong(0),value.optJSONArray("lines")?.length()?:0,value.optJSONArray("answers")?.length()?:0))}}}
            counts.forEach{(id,fragments,questions)->db.update("sessions",ContentValues().apply{put("fragments",fragments);put("questions",questions)},"id=?",arrayOf(id.toString()))}
        }
        if(oldVersion<3){
            db.execSQL("ALTER TABLE folders ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy'")
            db.execSQL("ALTER TABLE sessions ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'legacy'")
            rebuildOwnerScopedTables(db)
        }
    }
    private fun rebuildOwnerScopedTables(db:SQLiteDatabase){
        db.execSQL("CREATE TABLE folders_scoped(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE,owner_id TEXT NOT NULL,UNIQUE(owner_id,name))")
        db.execSQL("INSERT INTO folders_scoped(id,name,owner_id) SELECT id,name,owner_id FROM folders")
        db.execSQL("CREATE TABLE sessions_scoped(id INTEGER PRIMARY KEY,title TEXT NOT NULL,updated INTEGER NOT NULL,data TEXT NOT NULL,fragments INTEGER NOT NULL DEFAULT 0,questions INTEGER NOT NULL DEFAULT 0,folder_id INTEGER REFERENCES folders_scoped(id) ON DELETE SET NULL,owner_id TEXT NOT NULL)")
        db.execSQL("INSERT INTO sessions_scoped(id,title,updated,data,fragments,questions,folder_id,owner_id) SELECT id,title,updated,data,fragments,questions,folder_id,owner_id FROM sessions")
        db.execSQL("DROP TABLE sessions")
        db.execSQL("DROP TABLE folders")
        db.execSQL("ALTER TABLE folders_scoped RENAME TO folders")
        db.execSQL("ALTER TABLE sessions_scoped RENAME TO sessions")
        db.execSQL("CREATE INDEX sessions_folder ON sessions(owner_id,folder_id)")
    }
    private fun folderName(name:String)=name.trim().replace(Regex("\\s+")," ").take(80).also{require(it.isNotBlank()){"Escribe un nombre para la carpeta."}}
    fun folders():List<ConversationFolder> = readableDatabase.rawQuery("SELECT id,name FROM folders WHERE owner_id=? ORDER BY name COLLATE NOCASE",arrayOf(ownerId)).use{c->buildList{while(c.moveToNext())add(ConversationFolder(c.getLong(0),c.getString(1)))}}
    fun createFolder(name:String):Long{
        val value=folderName(name);folders().firstOrNull{ConversationRules.folded(it.name)==ConversationRules.folded(value)}?.let{return it.id};val db=writableDatabase
        db.insertWithOnConflict("folders",null,ContentValues().apply{put("name",value);put("owner_id",ownerId)},SQLiteDatabase.CONFLICT_IGNORE)
        return db.rawQuery("SELECT id FROM folders WHERE name=? COLLATE NOCASE AND owner_id=?",arrayOf(value,ownerId)).use{check(it.moveToFirst());it.getLong(0)}
    }
    fun renameFolder(id:Long,name:String){val value=folderName(name);require(folders().none{it.id!=id&&it.name.equals(value,true)}){"Ya existe una carpeta con ese nombre."};writableDatabase.update("folders",ContentValues().apply{put("name",value)},"id=? AND owner_id=?",arrayOf(id.toString(),ownerId))}
    fun deleteFolder(id:Long){writableDatabase.delete("folders","id=? AND owner_id=?",arrayOf(id.toString(),ownerId))}
    fun move(id:Long,folder:Long?){require(folder==null||folders().any{it.id==folder}){"Carpeta no disponible."};writableDatabase.update("sessions",ContentValues().apply{if(folder==null)putNull("folder_id")else put("folder_id",folder)},"id=? AND owner_id=?",arrayOf(id.toString(),ownerId))}

    fun list():List<ConversationEntry> = readableDatabase.rawQuery("SELECT id,title,updated,fragments,questions,folder_id,data FROM sessions WHERE owner_id=? ORDER BY updated DESC",arrayOf(ownerId)).use{c->buildList{while(c.moveToNext())add(ConversationEntry(c.getLong(0),if(JSONObject(c.getString(6)).has("automaticName"))JSONObject(c.getString(6)).let{data->ConversationNaming.saved(data.optString("name"),data.optString("automaticName"))}else ConversationNaming.display(decode(JSONObject(c.getString(6)),if(c.isNull(5))null else c.getLong(5))),c.getLong(2),c.getInt(3),c.getInt(4),if(c.isNull(5))null else c.getLong(5)))}}

    fun save(id:Long,state:AssistantState){
        if(state.lines.isEmpty()&&state.answers.isEmpty())return
        val data=JSONObject().put("summary",state.summary).put("name",state.conversationTitle).put("automaticName",ConversationNaming.automatic(state))
        data.put("organization",JSONObject().put("title",state.organization.title).put("map",state.organization.map?.let{ResearchedMapCodec.encode(it)}?:JSONObject.NULL).put("topics",JSONArray(state.organization.topics)).put("sections",JSONArray().apply{state.organization.sections.forEach{section->put(JSONObject().put("title",section.title).put("text",section.text).put("sources",JSONArray(section.sources)))}}).put("covered",JSONObject().apply{state.organization.covered.forEach{(id,revision)->put(id.toString(),revision)}}))
        data.put("lines",JSONArray().apply{state.lines.forEach{put(JSONObject().put("id",it.id).put("text",it.text).put("revision",it.revision).put("voice",it.voice).put("final",it.final).put("edited",it.edited))}})
        data.put("answers",JSONArray().apply{state.answers.forEach{put(JSONObject().put("id",it.id).put("source",it.source?:JSONObject.NULL).put("revision",it.revision).put("question",it.question).put("text",it.text).put("status",it.status).put("first",it.firstTextMs?:JSONObject.NULL).put("evidence",it.evidence).put("suggested",it.suggested).put("sources",JSONArray(it.supportingSources)))}})
        val title=ConversationNaming.display(state)
        val db=writableDatabase;db.beginTransaction()
        try{
            db.insertWithOnConflict("sessions",null,ContentValues().apply{put("id",id);put("title",title);put("updated",System.currentTimeMillis());put("data",data.toString());put("fragments",state.lines.size);put("questions",state.answers.size);put("owner_id",ownerId);state.folderId?.takeIf{folder->folders().any{it.id==folder}}?.let{put("folder_id",it)}},SQLiteDatabase.CONFLICT_IGNORE)
            db.update("sessions",ContentValues().apply{put("title",title);put("updated",System.currentTimeMillis());put("data",data.toString());put("fragments",state.lines.size);put("questions",state.answers.size)} ,"id=? AND owner_id=?",arrayOf(id.toString(),ownerId))
            db.setTransactionSuccessful()
        }finally{db.endTransaction()}
    }
    fun load(id:Long):AssistantState?=readableDatabase.rawQuery("SELECT data,folder_id FROM sessions WHERE id=? AND owner_id=?",arrayOf(id.toString(),ownerId)).use{c->if(!c.moveToFirst())null else decode(JSONObject(c.getString(0)),if(c.isNull(1))null else c.getLong(1))}
    private fun decode(data:JSONObject,folder:Long?):AssistantState{
        val lines=data.getJSONArray("lines");val answers=data.getJSONArray("answers")
        val org=data.optJSONObject("organization");val topics=org?.optJSONArray("topics");val sections=org?.optJSONArray("sections");val covered=org?.optJSONObject("covered")
        val organization=ClassOrganization(org?.optString("title").orEmpty(),if(topics==null)emptyList()else List(topics.length()){topics.optString(it)},if(sections==null)emptyList()else List(sections.length()){i->val section=sections.getJSONObject(i);val ids=section.getJSONArray("sources");OrganizedSection(section.getString("title"),section.getString("text"),List(ids.length()){ids.getLong(it)})},covered?.keys()?.asSequence()?.mapNotNull{key->key.toLongOrNull()?.let{it to covered.optInt(key)}}?.toMap().orEmpty(),ResearchedMapCodec.decode(org?.optJSONObject("map")))
        return AssistantState(folderId=folder,organization=organization,conversationTitle=data.optString("name"),automaticTitle=data.optString("automaticName"),lines=List(lines.length()){i->val l=lines.getJSONObject(i);SpeechLine(l.getLong("id"),l.getString("text"),l.optBoolean("final",true),l.getInt("revision"),l.getString("voice"),l.optBoolean("edited",true))},answers=List(answers.length()){i->val a=answers.getJSONObject(i);val status=a.getString("status");LiveAnswer(a.getString("id"),if(a.isNull("source"))null else a.getLong("source"),a.getInt("revision"),a.getString("question"),a.getString("text"),if(status=="En espera"||status.startsWith("Preparando")||status.startsWith("Respondiendo"))"Interrumpida al cerrar; texto conservado"else status,if(a.isNull("first"))null else a.getDouble("first"),a.optString("evidence"),a.optBoolean("suggested"),a.optJSONArray("sources")?.let{ids->List(ids.length()){ids.getLong(it)}}.orEmpty())},summary=data.optString("summary"))
    }
    fun rename(id:Long,title:String){
        val db=writableDatabase;db.beginTransaction()
        try{db.rawQuery("SELECT data FROM sessions WHERE id=? AND owner_id=?",arrayOf(id.toString(),ownerId)).use{cursor->
            if(cursor.moveToFirst()){val data=JSONObject(cursor.getString(0)).put("name",title);db.update("sessions",ContentValues().apply{put("title",title);put("data",data.toString())},"id=? AND owner_id=?",arrayOf(id.toString(),ownerId))}
        };db.setTransactionSuccessful()}finally{db.endTransaction()}
    }
    fun delete(id:Long){writableDatabase.delete("sessions","id=? AND owner_id=?",arrayOf(id.toString(),ownerId))}
    fun maxSessionId():Long=readableDatabase.rawQuery("SELECT COALESCE(MAX(id),0) FROM sessions",null).use{if(it.moveToFirst())it.getLong(0)else 0L}
    fun hasLegacyData():Boolean=readableDatabase.rawQuery("SELECT 1 FROM sessions WHERE owner_id='legacy' UNION ALL SELECT 1 FROM folders WHERE owner_id='legacy' LIMIT 1",null).use{it.moveToFirst()}
    fun assignLegacyDataToCurrentOwner(){
        require(ownerId!="legacy")
        val db=writableDatabase;db.beginTransaction()
        try{
            val legacy=mutableListOf<Pair<Long,String>>()
            db.rawQuery("SELECT id,name FROM folders WHERE owner_id='legacy'",null).use{c->while(c.moveToNext())legacy.add(c.getLong(0) to c.getString(1))}
            legacy.forEach{(oldId,name)->
                val existing=db.rawQuery("SELECT id FROM folders WHERE owner_id=? AND name=? COLLATE NOCASE LIMIT 1",arrayOf(ownerId,name)).use{c->if(c.moveToFirst())c.getLong(0)else null}
                if(existing!=null){
                    db.update("sessions",ContentValues().apply{put("owner_id",ownerId);put("folder_id",existing)},"owner_id='legacy' AND folder_id=?",arrayOf(oldId.toString()))
                    db.delete("folders","id=? AND owner_id='legacy'",arrayOf(oldId.toString()))
                }else db.update("folders",ContentValues().apply{put("owner_id",ownerId)},"id=? AND owner_id='legacy'",arrayOf(oldId.toString()))
            }
            db.update("sessions",ContentValues().apply{put("owner_id",ownerId)},"owner_id='legacy'",null)
            db.setTransactionSuccessful()
        }finally{db.endTransaction()}
    }
}
