"""CIVINITY dispatcher: server-side access control, PostgreSQL storage, time events and PN acts."""
import os, re, io, secrets, hashlib, math, json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from flask import Blueprint, request, jsonify, send_file, g
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Numeric, Boolean, LargeBinary, select, func
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape

bp=Blueprint('dispatch',__name__,url_prefix='/api/dispatch')
url=os.getenv('DATABASE_URL','').replace('postgres://','postgresql://',1)
engine=create_engine(url, pool_pre_ping=True) if url else None
Base=declarative_base()
Session=sessionmaker(bind=engine,expire_on_commit=False) if engine else None
NOW=lambda:datetime.now(timezone.utc)
D=lambda x:Decimal(str(x or 0)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
ROLES={'administrators','vaditajs','parvaldnieks','meistars','arpakalpojums'}

class User(Base):
 __tablename__='d_users'
 id=Column(Integer,primary_key=True); name=Column(String(160),nullable=False); email=Column(String(250),unique=True,nullable=False); password=Column(String(256),nullable=False); role=Column(String(40),default='meistars'); approved=Column(Boolean,default=False); active=Column(Boolean,default=True); created=Column(DateTime(timezone=True),default=NOW); department=Column(String(120),default=''); position=Column(String(120),default=''); avatar=Column(Text,default='')
class Token(Base):
 __tablename__='d_tokens'
 id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('d_users.id')); digest=Column(String(64),unique=True); expires=Column(DateTime(timezone=True))
class Object(Base):
 __tablename__='d_objects'
 id=Column(Integer,primary_key=True); name=Column(String(200)); address=Column(String(300),nullable=False); code=Column(String(80),unique=True); ownership=Column(String(100)); company=Column(String(60)); customer=Column(String(240)); contract=Column(String(120)); rate=Column(Numeric(12,2),default=0); vat=Column(Numeric(5,2),default=21); latitude=Column(Numeric(12,8)); longitude=Column(Numeric(12,8)); radius=Column(Integer,default=150); manager_id=Column(Integer,ForeignKey('d_users.id')); contract_included=Column(Boolean,default=False); cadastral_number=Column(String(90),default='')
class ObjectFile(Base):
 __tablename__='d_object_files'
 id=Column(Integer,primary_key=True); object_id=Column(Integer,ForeignKey('d_objects.id'),nullable=False,index=True); filename=Column(String(255),nullable=False); mime=Column(String(120),nullable=False); category=Column(String(32),nullable=False); content=Column(LargeBinary,nullable=False); created=Column(DateTime(timezone=True),default=NOW); uploader=Column(Integer,ForeignKey('d_users.id'))
class Rate(Base):
 __tablename__='d_rates'
 id=Column(Integer,primary_key=True); object_id=Column(Integer,ForeignKey('d_objects.id')); department=Column(String(120)); rate=Column(Numeric(12,2)); effective_from=Column(String(10))
class Task(Base):
 __tablename__='d_tasks'
 id=Column(Integer,primary_key=True); object_id=Column(Integer,ForeignKey('d_objects.id')); worker_id=Column(Integer,ForeignKey('d_users.id')); department=Column(String(100)); description=Column(Text); completed=Column(Text,default=''); status=Column(String(50),default='jauns'); payment=Column(String(30),default='included'); priority=Column(String(30),default='normal'); created_by=Column(Integer,ForeignKey('d_users.id')); approved_by=Column(Integer,ForeignKey('d_users.id')); approved_at=Column(DateTime(timezone=True)); completed_at=Column(DateTime(timezone=True)); created=Column(DateTime(timezone=True),default=NOW); rate_snapshot=Column(Numeric(12,2),default=0); material_total=Column(Numeric(12,2),default=0); manual_minutes=Column(Integer); correction_reason=Column(Text); pn_id=Column(Integer,ForeignKey('d_pn.id'))
class TaskAssignment(Base):
 __tablename__="d_task_assignments"
 id=Column(Integer,primary_key=True); task_id=Column(Integer,ForeignKey("d_tasks.id"),index=True); user_id=Column(Integer,ForeignKey("d_users.id"),index=True)
class TaskNotification(Base):
 __tablename__="d_task_notifications"
 id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey("d_users.id"),index=True); task_id=Column(Integer,ForeignKey("d_tasks.id")); seen=Column(Boolean,default=False); created=Column(DateTime(timezone=True),default=NOW)
class Event(Base):
 __tablename__='d_events'
 id=Column(Integer,primary_key=True); task_id=Column(Integer,ForeignKey('d_tasks.id')); user_id=Column(Integer,ForeignKey('d_users.id')); action=Column(String(40)); at=Column(DateTime(timezone=True),default=NOW); lat=Column(Numeric(12,8)); lon=Column(Numeric(12,8)); accuracy=Column(Numeric(10,2)); distance=Column(Numeric(10,2)); gps_status=Column(String(40)); note=Column(Text)
class Material(Base):
 __tablename__='d_materials'
 id=Column(Integer,primary_key=True); task_id=Column(Integer,ForeignKey('d_tasks.id')); name=Column(String(200)); unit=Column(String(30)); qty=Column(Numeric(12,3)); price=Column(Numeric(12,2))
class Photo(Base):
 __tablename__='d_photos'
 id=Column(Integer,primary_key=True); task_id=Column(Integer,ForeignKey('d_tasks.id')); mime=Column(String(30)); data=Column(LargeBinary); created=Column(DateTime(timezone=True),default=NOW)
class PN(Base):
 __tablename__='d_pn'
 id=Column(Integer,primary_key=True); object_id=Column(Integer,ForeignKey('d_objects.id')); year=Column(Integer); month=Column(Integer); status=Column(String(40),default='melnraksts'); created_by=Column(Integer,ForeignKey('d_users.id')); created=Column(DateTime(timezone=True),default=NOW); company_json=Column(Text,default='{}')
class Audit(Base):
 __tablename__='d_audit'
 id=Column(Integer,primary_key=True); actor=Column(Integer); kind=Column(String(80)); ref=Column(Integer); detail=Column(Text); at=Column(DateTime(timezone=True),default=NOW)

if engine:
 Base.metadata.create_all(engine)
 # Idempotent additive migration for existing PostgreSQL installations.
 from sqlalchemy import inspect, text as sql_text
 with engine.begin() as connection:
  existing={c['name'] for c in inspect(connection).get_columns('d_users')}
  for field, typ in [('department','VARCHAR(120)'),('position','VARCHAR(120)'),('avatar','TEXT')]:
   if field not in existing:
    connection.execute(sql_text(f'ALTER TABLE d_users ADD COLUMN {field} {typ}'))
  obj_columns={c['name'] for c in inspect(connection).get_columns('d_objects')}
  if 'cadastral_number' not in obj_columns:
   connection.execute(sql_text("ALTER TABLE d_objects ADD COLUMN cadastral_number VARCHAR(90) DEFAULT ''"))
 # Bootstrap administrator only with explicit environment credentials.
 if os.getenv('DISPATCH_ADMIN_EMAIL') and os.getenv('DISPATCH_ADMIN_PASSWORD'):
  with Session.begin() as s:
   email=os.getenv('DISPATCH_ADMIN_EMAIL').strip().lower()
   if not s.query(User).filter_by(email=email).first():
    s.add(User(name='Administrator',email=email,password=generate_password_hash(os.environ['DISPATCH_ADMIN_PASSWORD']),role='administrators',approved=True))

def error(msg,code=400):return jsonify(error=msg),code
def need_db():
 if not engine:return error('DATABASE_URL nav konfigurēts',503)
def auth(f):
 @wraps(f)
 def inner(*args,**kwargs):
  if not engine:return error('DATABASE_URL nav konfigurēts',503)
  raw=request.headers.get('Authorization','').removeprefix('Bearer ').strip()
  if not raw:return error('Nepieciešama autorizācija',401)
  s=Session();g.db=s
  try:
   token=s.query(Token).filter_by(digest=hashlib.sha256(raw.encode()).hexdigest()).first()
   u=s.get(User,token.user_id) if token and token.expires.replace(tzinfo=timezone.utc)>NOW() else None
   if not u or not u.active or not u.approved:return error('Nav piekļuves',403)
   g.user=u
   return f(*args,**kwargs)
  finally:s.close()
 return inner
def allowed(*roles):return g.user.role in roles or g.user.role=='administrators'
def guard(*roles):return None if allowed(*roles) else error('Nepietiek tiesību',403)
def audit(kind,ref,detail=''):g.db.add(Audit(actor=g.user.id,kind=kind,ref=ref,detail=detail))
def json_user(u):return dict(id=u.id,name=u.name,email=u.email,role=u.role,approved=u.approved,department=u.department or '',position=u.position or '',avatar=u.avatar or '')
def obj_dict(o):return dict(id=o.id,name=o.name,address=o.address,code=o.code,ownership=o.ownership,company=o.company,customer=o.customer,contract=o.contract,rate=float(o.rate or 0),vat=float(o.vat or 21),latitude=float(o.latitude) if o.latitude is not None else None,longitude=float(o.longitude) if o.longitude is not None else None,radius=o.radius,manager_id=o.manager_id,cadastral_number=o.cadastral_number or '')
def object_access(o):return allowed('vaditajs') or (g.user.role=='parvaldnieks' and o.manager_id==g.user.id)
def task_access(t):
 o=g.db.get(Object,t.object_id)
 return object_access(o) or t.worker_id==g.user.id or g.db.query(TaskAssignment).filter_by(task_id=t.id,user_id=g.user.id).first() is not None

def minutes(t):
 if t.manual_minutes is not None:return t.manual_minutes
 events=g.db.query(Event).filter_by(task_id=t.id).order_by(Event.at,Event.id).all(); start=None; total=0
 for e in events:
  if e.action in ('start','resume') and start is None:start=e.at
  elif e.action in ('pause','finish') and start is not None:
   total+=max(0,int((e.at.replace(tzinfo=timezone.utc)-start.replace(tzinfo=timezone.utc)).total_seconds()//60));start=None
 if start:total+=max(0,int((NOW()-start.replace(tzinfo=timezone.utc)).total_seconds()//60))
 return total

def task_dict(t):
 o=g.db.get(Object,t.object_id); u=g.db.get(User,t.worker_id) if t.worker_id else None
 mats=g.db.query(Material).filter_by(task_id=t.id).all(); mins=minutes(t); labor=D(Decimal(mins)*D(t.rate_snapshot)/Decimal(60)); mt=sum((D(m.qty)*D(m.price) for m in mats),Decimal(0)); total=D(labor+mt)
 return dict(assignee_ids=[a.user_id for a in g.db.query(TaskAssignment).filter_by(task_id=t.id).all()] or ([t.worker_id] if t.worker_id else []),id=t.id,number=f'UZ-{t.id:06d}',object_id=t.object_id,object=o.address if o else '',object_code=o.code if o else '',worker_id=t.worker_id,worker=u.name if u else '',department=t.department,description=t.description,completed=t.completed,status=t.status,payment=t.payment,priority=t.priority,created=t.created.isoformat(),completed_at=t.completed_at.isoformat() if t.completed_at else None,minutes=mins,hours=round(mins/60,2),rate=float(t.rate_snapshot or 0),labor=float(labor),materials=float(mt),total=float(total),pn_id=t.pn_id,materials_list=[dict(id=m.id,name=m.name,unit=m.unit,qty=float(m.qty),price=float(m.price)) for m in mats])

@bp.post('/register')
def register():
 if not engine:return error('DATABASE_URL nav konfigurēts',503)
 p=request.get_json(silent=True) or {}; email=str(p.get('email','')).strip().lower();password=str(p.get('password',''))
 if '@' not in email or len(password)<12 or not str(p.get('name','')).strip():return error('Vārds, e-pasts un parole (vismaz 12 zīmes) ir obligāti')
 with Session.begin() as s:
  if s.query(User).filter_by(email=email).first():return error('E-pasts jau reģistrēts',409)
  s.add(User(name=p['name'].strip(),email=email,password=generate_password_hash(password),role='meistars',approved=False))
 return jsonify(message='Reģistrācija nosūtīta administratoram'),201
@bp.post('/login')
def login():
 if not engine:return error('DATABASE_URL nav konfigurēts',503)
 p=request.get_json(silent=True) or {}
 with Session.begin() as s:
  u=s.query(User).filter_by(email=str(p.get('email','')).lower().strip()).first()
  if not u or not check_password_hash(u.password,str(p.get('password',''))):return error('Nepareizi piekļuves dati',401)
  if not u.approved or not u.active:return error('Konts gaida administratora apstiprinājumu',403)
  raw=secrets.token_urlsafe(48);s.add(Token(user_id=u.id,digest=hashlib.sha256(raw.encode()).hexdigest(),expires=NOW()+timedelta(days=7)))
  return jsonify(token=raw,user=json_user(u))
@bp.post('/logout')
@auth
def logout():
 raw=request.headers.get('Authorization','').removeprefix('Bearer ').strip();g.db.query(Token).filter_by(digest=hashlib.sha256(raw.encode()).hexdigest()).delete();g.db.commit();return jsonify(ok=True)
@bp.get('/me')
@auth
def me():return jsonify(json_user(g.user))
@bp.patch('/me')
@auth
def update_my_profile():
 p=request.get_json(silent=True) or {}
 u=g.user
 if 'name' in p:
  name=str(p['name']).strip()
  if len(name)<2 or len(name)>160:return error('Vārds jānorāda 2–160 rakstzīmēs')
  u.name=name
 if 'position' in p:
  value=str(p['position']).strip()
  if len(value)>120:return error('Amats pārāk garš')
  u.position=value
 if 'avatar' in p:
  value=str(p['avatar'])
  if value and (len(value)>180000 or not re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+',value)):
   return error('Atļauts tikai neliels PNG, JPEG vai WebP attēls')
  u.avatar=value
 # Department, role, approval and email remain administrator-managed.
 audit('profile_updated',u.id);g.db.commit()
 return jsonify(json_user(u))

@bp.get('/me/stats')
@auth
def my_statistics():
 q=g.db.query(Task).filter_by(worker_id=g.user.id)
 rows=q.all()
 approved=[t for t in rows if t.status in ('apstiprinats','pabeigts')]
 return jsonify(assigned=len(rows),completed=len(approved),active=len([t for t in rows if t.status not in ('apstiprinats','pabeigts','atcelts')]),minutes=sum(minutes(t) for t in approved))

@bp.get('/users')
@auth
def users():
 if not allowed('vaditajs','parvaldnieks'):return error('Nav piekļuves',403)
 return jsonify([json_user(u) for u in g.db.query(User).order_by(User.name).all() if allowed('vaditajs') or u.approved])
@bp.patch('/users/<int:uid>')
@auth
def user_update(uid):
 if not allowed():return error('Tikai administrators',403)
 u=g.db.get(User,uid)
 if not u:return error('Nav atrasts',404)
 p=request.get_json(silent=True) or {}
 if 'role' in p:
  if p['role'] not in ROLES:return error('Nepareiza loma')
  u.role=p['role']
 if 'approved' in p:u.approved=bool(p['approved'])
 if 'active' in p:u.active=bool(p['active'])
 if 'department' in p:u.department=str(p['department']).strip()[:120]
 if 'position' in p:u.position=str(p['position']).strip()[:120]
 audit('user_update',uid,json.dumps(p));g.db.commit();return jsonify(json_user(u))
@bp.get('/objects')
@auth
def objects():
 q=g.db.query(Object)
 if g.user.role=='parvaldnieks':q=q.filter_by(manager_id=g.user.id)
 if g.user.role in ('meistars','arpakalpojums'):
  ids=[x[0] for x in g.db.query(Task.object_id).filter_by(worker_id=g.user.id).distinct().all()];q=q.filter(Object.id.in_(ids))
 return jsonify([obj_dict(o) for o in q.order_by(Object.address).all()])
@bp.post('/objects')
@auth
def create_object():
 if e:=guard('vaditajs'):return e
 p=request.get_json(silent=True) or {}
 if not p.get('code'):
  import uuid
  p['code']='OBJ-'+uuid.uuid4().hex[:12]
 if p.get('address') is None:p['address']=''
 o=Object(**{k:p.get(k) for k in ('name','address','code','ownership','company','customer','contract','rate','vat','latitude','longitude','radius','manager_id','cadastral_number') if k in p});g.db.add(o)
 try:g.db.flush();audit('object_created',o.id);g.db.commit()
 except Exception:g.db.rollback();return error('Objekta kods jau eksistē vai dati neder',409)
 return jsonify(obj_dict(o)),201
@bp.patch('/objects/<int:oid>')
@auth
def update_object(oid):
 o=g.db.get(Object,oid)
 if not o:return error('Nav atrasts',404)
 if not object_access(o):return error('Nav piekļuves',403)
 p=request.get_json(silent=True) or {}
 for k in ('name','address','ownership','company','customer','contract','rate','vat','latitude','longitude','radius','manager_id','cadastral_number'):
  if k in p:setattr(o,k,p[k])
 audit('object_updated',oid,json.dumps(p));g.db.commit();return jsonify(obj_dict(o))
def object_visible(o):
 if not o:return False
 if object_access(o):return True
 if g.user.role in ('meistars','arpakalpojums'):
  return g.db.query(Task.id).filter_by(object_id=o.id,worker_id=g.user.id).first() is not None
 return False

@bp.get('/objects/<int:oid>/files')
@auth
def object_files(oid):
 o=g.db.get(Object,oid)
 if not object_visible(o):return error('Nav piekļuves',403)
 rows=g.db.query(ObjectFile).filter_by(object_id=oid).order_by(ObjectFile.created.desc()).all()
 return jsonify([dict(id=x.id,filename=x.filename,mime=x.mime,category=x.category,created=x.created.isoformat() if x.created else '') for x in rows])

@bp.post('/objects/<int:oid>/files')
@auth
def object_file_upload(oid):
 o=g.db.get(Object,oid)
 if not o or not object_access(o):return error('Nav piekļuves',403)
 file=request.files.get('file'); category=request.form.get('category','document')
 if category not in ('document','cadastre','photo'):return error('Nepareiza kategorija')
 if not file or not file.filename:return error('Izvēlieties failu')
 content=file.read(10*1024*1024+1)
 if not content or len(content)>10*1024*1024:return error('Fails nedrīkst pārsniegt 10 MB',413)
 from werkzeug.utils import secure_filename
 filename=secure_filename(file.filename) or 'dokuments'
 mime=(file.mimetype or '').lower()
 allowed_types={'application/pdf','image/jpeg','image/png','image/webp','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
 if mime not in allowed_types:return error('Atļauti PDF, JPG, PNG, WEBP, DOC, DOCX, XLS, XLSX')
 if category=='photo' and not mime.startswith('image/'):return error('Fotogrāfijai jābūt attēlam')
 if category=='cadastre' and mime not in ('application/pdf','image/jpeg','image/png','image/webp'):return error('Kadastram nepieciešams PDF vai attēls')
 if category in ('cadastre','photo'):
  g.db.query(ObjectFile).filter_by(object_id=oid,category=category).delete(synchronize_session=False)
 record=ObjectFile(object_id=oid,filename=filename,mime=mime,category=category,content=content,uploader=g.user.id)
 g.db.add(record);g.db.flush();audit('object_file_uploaded',oid,category+':'+filename);g.db.commit()
 return jsonify(id=record.id,filename=filename,category=category),201

@bp.get('/objects/<int:oid>/files/<int:fid>')
@auth
def object_file_download(oid,fid):
 o=g.db.get(Object,oid)
 if not object_visible(o):return error('Nav piekļuves',403)
 file=g.db.query(ObjectFile).filter_by(id=fid,object_id=oid).first()
 if not file:return error('Fails nav atrasts',404)
 return send_file(io.BytesIO(file.content),mimetype=file.mime,as_attachment=(request.args.get('download')=='1'),download_name=file.filename)

@bp.delete('/objects/<int:oid>/files/<int:fid>')
@auth
def object_file_delete(oid,fid):
 o=g.db.get(Object,oid)
 if not o or not object_access(o):return error('Nav piekļuves',403)
 file=g.db.query(ObjectFile).filter_by(id=fid,object_id=oid).first()
 if not file:return error('Fails nav atrasts',404)
 g.db.delete(file);audit('object_file_deleted',oid,str(fid));g.db.commit();return jsonify(ok=True)

@bp.get('/tasks')
@auth
def tasks():
 q=g.db.query(Task)
 if g.user.role in ('meistars','arpakalpojums'):
  from sqlalchemy import or_
  assigned=g.db.query(TaskAssignment.task_id).filter_by(user_id=g.user.id)
  q=q.filter(or_(Task.worker_id==g.user.id,Task.id.in_(assigned)))
 elif g.user.role=='parvaldnieks':q=q.filter(Task.object_id.in_([o.id for o in g.db.query(Object).filter_by(manager_id=g.user.id)]))
 return jsonify([task_dict(t) for t in q.order_by(Task.id.desc()).limit(500).all()])
@bp.post('/tasks')
@auth
def task_create():
 if e:=guard('vaditajs','parvaldnieks'):return e
 p=request.get_json(silent=True) or {};o=g.db.get(Object,p.get('object_id'))
 if not o or not object_access(o):return error('Objekts nav pieejams',403)
 ids=p.get('worker_ids') or ([p.get('worker_id')] if p.get('worker_id') else [])
 try:ids=list(dict.fromkeys(int(x) for x in ids))
 except (ValueError,TypeError):return error('Nekorekti meistaru ID')
 if not ids or len(ids)>20:return error('Izvēlieties 1–20 meistarus')
 assignees=g.db.query(User).filter(User.id.in_(ids),User.approved.is_(True),User.active.is_(True),User.role=='meistars').all()
 if len(assignees)!=len(ids):return error('Izvēlieties tikai apstiprinātus meistarus')
 u=assignees[0]
 department=str(p.get('department',''));rate=o.rate
 rate_row=g.db.query(Rate).filter_by(object_id=o.id,department=department).order_by(Rate.effective_from.desc()).first()
 if rate_row:rate=rate_row.rate
 if p.get('payment') not in ('included','extra'):return error('Nepieciešams darba apmaksas veids')
 t=Task(object_id=o.id,worker_id=u.id,department=department,description=str(p.get('description','')),payment=p['payment'],priority=p.get('priority','normal'),created_by=g.user.id,status='nodots',rate_snapshot=rate)
 g.db.add(t);g.db.flush()
 for uid in ids:
  g.db.add(TaskAssignment(task_id=t.id,user_id=uid))
  g.db.add(TaskNotification(task_id=t.id,user_id=uid))
 audit('task_created',t.id);g.db.commit();return jsonify(task_dict(t)),201
@bp.patch('/tasks/<int:tid>')
@auth
def task_edit(tid):
 t=g.db.get(Task,tid)
 if not t or not task_access(t):return error('Nav piekļuves',403)
 if t.pn_id or t.status=='apstiprinats':return error('Apstiprināts vai aktā iekļauts uzdevums nav maināms',409)
 p=request.get_json(silent=True) or {}
 if 'completed' in p:t.completed=str(p['completed'])[:12000]
 if 'materials' in p:
  if not isinstance(p['materials'],list) or len(p['materials'])>100:return error('Materiālu saraksts neder')
  g.db.query(Material).filter_by(task_id=t.id).delete()
  for m in p['materials']:
   if D(m.get('qty'))<0 or D(m.get('price'))<0:return error('Nederīga materiāla cena vai daudzums')
   g.db.add(Material(task_id=t.id,name=str(m.get('name',''))[:200],unit=str(m.get('unit','gab.'))[:30],qty=m.get('qty',0),price=m.get('price',0)))
 if 'worker_id' in p and allowed('vaditajs','parvaldnieks'):
  u=g.db.get(User,p['worker_id']);
  if not u or not u.approved:return error('Izpildītājs nav apstiprināts')
  t.worker_id=u.id
 if 'manual_minutes' in p:
  if not allowed('vaditajs','parvaldnieks') or not str(p.get('correction_reason','')).strip():return error('Labojumam vajadzīgas tiesības un pamatojums',403)
  t.manual_minutes=max(0,int(p['manual_minutes']));t.correction_reason=p['correction_reason']
 if p.get('submit'):
  if not t.completed.strip():return error('Aizpildiet paveikto darbu aprakstu')
  t.status='gaida_apstiprinajumu';t.completed_at=NOW()
 audit('task_updated',t.id,json.dumps({k:v for k,v in p.items() if k!='materials'},ensure_ascii=False));g.db.commit();return jsonify(task_dict(t))
def haversine(a,b,c,d):
 R=6371000;phi1,phi2=math.radians(a),math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b);v=math.sin(dp/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(v),math.sqrt(1-v))
@bp.post('/tasks/<int:tid>/clock')
@auth
def clock(tid):
 t=g.db.get(Task,tid)
 if not t or t.worker_id!=g.user.id:return error('Uzdevums nav piešķirts',403)
 if t.pn_id or t.status in ('apstiprinats','gaida_apstiprinajumu'):return error('Uzdevums ir slēgts',409)
 p=request.get_json(silent=True) or {};action=p.get('action');events=g.db.query(Event).filter_by(task_id=tid).order_by(Event.id.desc()).all();last=events[0].action if events else None
 if (action,last) not in [('start',None),('pause','start'),('pause','resume'),('resume','pause'),('finish','start'),('finish','resume')]:return error('Nepareiza darba laika darbība',409)
 o=g.db.get(Object,t.object_id);lat=p.get('lat');lon=p.get('lon');accuracy=p.get('accuracy');dist=None;gps='unavailable'
 if lat is not None and lon is not None:
  try:
   lat=float(lat);lon=float(lon);accuracy=float(accuracy or 9999)
   if not (-90<=lat<=90 and -180<=lon<=180):raise ValueError()
   dist=haversine(lat,lon,float(o.latitude),float(o.longitude)) if o.latitude is not None and o.longitude is not None else None
   gps='unconfigured' if dist is None else ('uncertain' if accuracy>100 else ('inside' if dist<=o.radius else 'outside'))
  except (ValueError,TypeError):return error('GPS koordinātas neder')
 e=Event(task_id=tid,user_id=g.user.id,action=action,lat=lat,lon=lon,accuracy=accuracy,distance=dist,gps_status=gps,note=str(p.get('note',''))[:1000]);g.db.add(e)
 t.status='procesa' if action!='finish' else 'pabeigts'
 if action=='finish':t.completed_at=NOW()
 g.db.flush();audit('clock_'+action,tid,gps);g.db.commit();return jsonify(task_dict(t))
@bp.get('/tasks/<int:tid>/events')
@auth
def events(tid):
 t=g.db.get(Task,tid)
 if not t or not task_access(t):return error('Nav piekļuves',403)
 return jsonify([dict(action=e.action,at=e.at.isoformat(),gps=e.gps_status,accuracy=float(e.accuracy) if e.accuracy is not None else None,distance=float(e.distance) if e.distance is not None else None) for e in g.db.query(Event).filter_by(task_id=tid).order_by(Event.id).all()])
@bp.post('/tasks/<int:tid>/photo')
@auth
def photo_upload(tid):
 t=g.db.get(Task,tid)
 if not t or not task_access(t) or t.status in ('apstiprinats','gaida_apstiprinajumu') or t.pn_id:return error('Nav piekļuves',403)
 f=request.files.get('photo')
 if not f:return error('Nav faila')
 data=f.read(4*1024*1024+1)
 if len(data)>4*1024*1024:return error('Attēls pārsniedz 4 MB')
 from PIL import Image
 try:
  im=Image.open(io.BytesIO(data));im.verify()
  if im.format not in ('JPEG','PNG','WEBP'):raise ValueError()
 except Exception:return error('Atļauti tikai JPEG, PNG, WEBP attēli')
 g.db.add(Photo(task_id=tid,mime='image/'+im.format.lower(),data=data));audit('photo_uploaded',tid);g.db.commit();return jsonify(ok=True)
@bp.get('/tasks/<int:tid>/photos')
@auth
def photo_list(tid):
 t=g.db.get(Task,tid)
 if not t or not task_access(t):return error('Nav piekļuves',403)
 return jsonify([dict(id=p.id,mime=p.mime) for p in g.db.query(Photo).filter_by(task_id=tid).all()])
@bp.get('/photos/<int:pid>')
@auth
def photo_get(pid):
 p=g.db.get(Photo,pid)
 if not p or not task_access(g.db.get(Task,p.task_id)):return error('Nav piekļuves',403)
 return send_file(io.BytesIO(p.data),mimetype=p.mime)
@bp.post('/tasks/<int:tid>/review')
@auth
def review(tid):
 t=g.db.get(Task,tid)
 if not t or t.status!='gaida_apstiprinajumu':return error('Uzdevums nav iesniegts',409)
 o=g.db.get(Object,t.object_id)
 if not object_access(o):return error('Nav piekļuves',403)
 if t.worker_id==g.user.id:return error('Izpildītājs nevar apstiprināt savu darbu',403)
 p=request.get_json(silent=True) or {};decision=p.get('decision')
 if decision not in ('approve','return'):return error('Lēmums nav norādīts')
 t.status='apstiprinats' if decision=='approve' else 'atgriezts';t.approved_by=g.user.id if decision=='approve' else None;t.approved_at=NOW() if decision=='approve' else None
 audit('review_'+decision,tid,str(p.get('comment',''))[:1000]);g.db.commit();return jsonify(task_dict(t))
@bp.post('/ai-report')
@auth
def ai_report():
 p=request.get_json(silent=True) or {};raw=str(p.get('text',''))[:6000]
 if not raw.strip():return error('Ierunājiet vai ievadiet tekstu')
 if not os.getenv('OPENAI_API_KEY'):return error('OPENAI_API_KEY nav konfigurēts',503)
 from openai import OpenAI
 try:
  r=OpenAI().chat.completions.create(model=os.getenv('DISPATCH_AI_MODEL','gpt-4o-mini'),messages=[{'role':'system','content':'Pārraksti meistara faktisko darbu atskaiti profesionālā latviešu valodā. Nekad neizdomā neizdarītus darbus, pārbaudes, materiālus, rezultātus vai laikus. Atbildi tikai ar gatavu aprakstu.'},{'role':'user','content':raw}],temperature=0.1)
  return jsonify(text=r.choices[0].message.content)
 except Exception:return error('AI pakalpojums šobrīd nav pieejams',502)
@bp.get('/notifications')
@auth
def task_notifications():
 rows=g.db.query(TaskNotification).filter_by(user_id=g.user.id).order_by(TaskNotification.id.desc()).limit(100).all()
 return jsonify([dict(id=n.id,task_id=n.task_id,seen=n.seen,created=n.created.isoformat()) for n in rows])

@bp.post('/notifications/<int:nid>/read')
@auth
def task_notification_read(nid):
 n=g.db.query(TaskNotification).filter_by(id=nid,user_id=g.user.id).first()
 if not n:return error('Nav piekļuves',404)
 n.seen=True;g.db.commit();return jsonify(ok=True)

@bp.post('/ai-task')
@auth
def ai_task():
 p=request.get_json(silent=True) or {};raw=str(p.get('text',''))[:8000]
 if not raw.strip():return error('Nav teksta')
 if not os.getenv('OPENAI_API_KEY'):return error('AI nav konfigurēts (OPENAI_API_KEY)',503)
 from openai import OpenAI
 try:
  r=OpenAI().chat.completions.create(model=os.getenv('DISPATCH_AI_MODEL','gpt-4o-mini'),messages=[{'role':'system','content':'Pārveido diktētu darba uzdevumu īsā, precīzā un profesionālā latviešu valodas darba aprakstā. Saglabā visus faktus, adreses, izmērus, apjomus, skaitļus un tehniskās prasības. Neizdomā neko, kas nav teikts. Atgriez tikai gatavo tekstu.'},{'role':'user','content':raw}],temperature=0.1)
  return jsonify(text=r.choices[0].message.content)
 except Exception:return error('AI apstrāde neizdevās',502)

@bp.post('/transcribe-task')
@auth
def transcribe_task():
 if not os.getenv('OPENAI_API_KEY'):return error('AI nav konfigurēts (OPENAI_API_KEY)',503)
 f=request.files.get('audio')
 if not f:return error('Nav audio faila')
 data=f.read(12*1024*1024+1)
 if len(data)>12*1024*1024:return error('Audio pārsniedz 12 MB')
 from openai import OpenAI
 try:
  buf=io.BytesIO(data);buf.name='uzdevums.webm' if 'webm' in (f.mimetype or '') else 'uzdevums.mp4'
  transcript=OpenAI().audio.transcriptions.create(model='whisper-1',file=buf,language='lv')
  return jsonify(text=transcript.text)
 except Exception:return error('Audio atpazīšana neizdevās',502)

@bp.get('/monthly')
@auth
def monthly():
 if e:=guard('vaditajs','parvaldnieks'):return e
 year=int(request.args.get('year',NOW().year));month=int(request.args.get('month',NOW().month));oid=request.args.get('object_id',type=int)
 q=g.db.query(Task).filter(Task.status=='apstiprinats',Task.completed_at>=datetime(year,month,1,tzinfo=timezone.utc),Task.completed_at<(datetime(year+1,1,1,tzinfo=timezone.utc) if month==12 else datetime(year,month+1,1,tzinfo=timezone.utc)))
 if oid:q=q.filter_by(object_id=oid)
 if g.user.role=='parvaldnieks':q=q.filter(Task.object_id.in_([o.id for o in g.db.query(Object).filter_by(manager_id=g.user.id)]))
 ts=q.all();return jsonify(tasks=[task_dict(t) for t in ts],total=round(sum(task_dict(t)['total'] for t in ts),2))
@bp.post('/pn')
@auth
def pn_create():
 if e:=guard('vaditajs','parvaldnieks'):return e
 p=request.get_json(silent=True) or {};o=g.db.get(Object,p.get('object_id'))
 if not o or not object_access(o):return error('Objekts nav pieejams',403)
 year=int(p.get('year'));month=int(p.get('month'))
 if not 1<=month<=12:return error('Nepareizs mēnesis')
 start=datetime(year,month,1,tzinfo=timezone.utc);end=datetime(year+1,1,1,tzinfo=timezone.utc) if month==12 else datetime(year,month+1,1,tzinfo=timezone.utc)
 ts=g.db.query(Task).filter(Task.object_id==o.id,Task.status=='apstiprinats',Task.payment=='extra',Task.pn_id.is_(None),Task.completed_at>=start,Task.completed_at<end).all()
 if not ts:return error('Nav apstiprinātu papildu maksas darbu šajā mēnesī')
 pn=PN(object_id=o.id,year=year,month=month,created_by=g.user.id,company_json=json.dumps(p.get('company',{}),ensure_ascii=False));g.db.add(pn);g.db.flush()
 for t in ts:t.pn_id=pn.id
 audit('pn_created',pn.id,f'{len(ts)} uzdevumi');g.db.commit();return jsonify(id=pn.id,number=f'PN-{year}-{month:02d}-{pn.id:04d}',count=len(ts)),201
@bp.get('/pn')
@auth
def pn_list():
 if e:=guard('vaditajs','parvaldnieks'):return e
 q=g.db.query(PN)
 if g.user.role=='parvaldnieks':q=q.filter(PN.object_id.in_([o.id for o in g.db.query(Object).filter_by(manager_id=g.user.id)]))
 return jsonify([dict(id=p.id,number=f'PN-{p.year}-{p.month:02d}-{p.id:04d}',object=g.db.get(Object,p.object_id).address,status=p.status) for p in q.order_by(PN.id.desc()).all()])
@bp.patch('/pn/<int:pid>')
@auth
def pn_status(pid):
 p=g.db.get(PN,pid)
 if not p or not object_access(g.db.get(Object,p.object_id)):return error('Nav piekļuves',403)
 status=(request.get_json(silent=True) or {}).get('status')
 if status not in ('apstiprinats','nosutits','parakstits'):return error('Nepareizs statuss')
 p.status=status;audit('pn_status',pid,status);g.db.commit();return jsonify(ok=True)
@bp.get('/pn/<int:pid>/pdf')
@auth
def pn_pdf(pid):
 p=g.db.get(PN,pid)
 if not p or not object_access(g.db.get(Object,p.object_id)):return error('Nav piekļuves',403)
 o=g.db.get(Object,p.object_id);ts=g.db.query(Task).filter_by(pn_id=pid).order_by(Task.id).all();company=json.loads(p.company_json or '{}');out=io.BytesIO()
 font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
 if os.path.isfile(font):
  if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('DejaVu',font))
  face='DejaVu'
 else:face='Helvetica'
 styles=getSampleStyleSheet();normal=ParagraphStyle('lv',parent=styles['Normal'],fontName=face,fontSize=8,leading=11);head=ParagraphStyle('lvh',parent=normal,fontSize=14,leading=19,spaceAfter=10)
 doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=27,rightMargin=27,topMargin=28,bottomMargin=28)
 para=lambda x:Paragraph(escape(str(x or '')),normal)
 elements=[Paragraph('PIEŅEMŠANAS–NODOŠANAS AKTS',head),para(f"{company.get('name') or company.get('legalName') or o.company or 'Pakalpojuma sniedzējs'}"),para(f"Reģ. Nr.: {company.get('reg') or company.get('regNo') or ''} | PVN Nr.: {company.get('vat') or ''}"),para(f"Adrese: {company.get('address') or ''}"),Spacer(1,9),para(f'Akts: PN-{p.year}-{p.month:02d}-{p.id:04d}   |   Periods: {p.month:02d}.{p.year}'),para(f'Pasūtītājs: {o.customer or "—"}  |  Objekts: {o.address}  |  Kods: {o.code}  |  Līgums: {o.contract or "—"}'),Spacer(1,12)]
 rows=[[para(x) for x in ['Nr.','Uzdevums','Paveiktie darbi','Stundas','EUR/h','Darbi EUR','Materiāli EUR','Kopā EUR']]]
 labor=Decimal(0);materials=Decimal(0)
 for i,t in enumerate(ts,1):
  d=task_dict(t);labor+=D(d['labor']);materials+=D(d['materials']);rows.append([para(i),para(d['number']),para(t.completed or t.description),para(d['hours']),para(d['rate']),para(f"{d['labor']:.2f}"),para(f"{d['materials']:.2f}"),para(f"{d['total']:.2f}")])
 subtotal=D(labor+materials);vat=D(subtotal*D(o.vat)/100);rows.append([para(''),para(''),para('KOPĀ'),para(''),para(''),para(f'{labor:.2f}'),para(f'{materials:.2f}'),para(f'{subtotal:.2f}')])
 tab=Table(rows,colWidths=[28,75,320,52,55,78,84,80],repeatRows=1,hAlign='LEFT');tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#173b60')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#b6c2cd')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e8eef5')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]));elements.extend([tab,Spacer(1,15),para(f'Kopā bez PVN: {subtotal:.2f} EUR'),para(f'PVN {o.vat}%: {vat:.2f} EUR'),para(f'KOPĀ AR PVN: {D(subtotal+vat):.2f} EUR'),Spacer(1,24),para('Pakalpojuma sniedzējs: ____________________     Pasūtītājs: ____________________')])
 elements.extend([Spacer(1,18),Paragraph('PIELIKUMS — IZLIETOTO MATERIĀLU SPECIFIKĀCIJA',head)])
 for t in ts:
  mats=g.db.query(Material).filter_by(task_id=t.id).all()
  if mats:
   elements.append(para(f'Uzdevums UZ-{t.id:06d}'))
   for m in mats:elements.append(para(f'{m.name}: {m.qty} {m.unit} × {m.price} EUR = {D(D(m.qty)*D(m.price))} EUR'))
 doc.build(elements);out.seek(0)
 return send_file(out,mimetype='application/pdf',as_attachment=True,download_name=f'PN-{p.year}-{p.month:02d}-{p.id:04d}.pdf')


@bp.get('/invoices/<int:pid>/pdf')
@auth
def invoice_pdf(pid):
 """Invoice draft from PN; restricted on server to administrators and vaditajs."""
 if e:=guard('vaditajs'):return e
 pn=g.db.get(PN,pid)
 if not pn:return error('Akts nav atrasts',404)
 o=g.db.get(Object,pn.object_id)
 if not o:return error('Objekts nav atrasts',404)
 ts=g.db.query(Task).filter_by(pn_id=pid).order_by(Task.id).all()
 if not ts:return error('Aktā nav darbu',400)
 company=json.loads(pn.company_json or '{}')
 out=io.BytesIO()
 font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
 if os.path.isfile(font):
  if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('DejaVu',font))
  face='DejaVu'
 else:face='Helvetica'
 styles=getSampleStyleSheet(); normal=ParagraphStyle('invnormal',parent=styles['Normal'],fontName=face,fontSize=9,leading=13)
 title=ParagraphStyle('invtitle',parent=normal,fontSize=18,leading=23,spaceAfter=15)
 para=lambda x:Paragraph(escape(str(x if x is not None else '')),normal)
 doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=36,rightMargin=36,topMargin=36,bottomMargin=36)
 supplier=company.get('name') or company.get('legalName') or o.company or ''
 elements=[Paragraph('RĒĶINA PROJEKTS',title),para('Dokumenta numurs: INV-PN-'+str(pn.year)+'-'+str(pn.month).zfill(2)+'-'+str(pn.id).zfill(4)),para('Datums: '+NOW().strftime('%d.%m.%Y')),Spacer(1,12),para('Pakalpojuma sniedzējs: '+supplier),para('Reģ. Nr.: '+str(company.get('reg') or company.get('regNo') or '—')),para('PVN Nr.: '+str(company.get('vat') or '—')),para('Adrese: '+str(company.get('address') or '—')),Spacer(1,9),para('Pasūtītājs: '+str(o.customer or '—')),para('Objekts: '+str(o.address)),para('Pamatojums: PN-'+str(pn.year)+'-'+str(pn.month).zfill(2)+'-'+str(pn.id).zfill(4)),Spacer(1,14)]
 rows=[[para('Nr.'),para('Darbi'),para('Summa bez PVN, EUR')]]
 total=Decimal('0')
 for i,t in enumerate(ts,1):
  d=task_dict(t);amount=D(d['total']);total+=amount
  rows.append([para(i),para(t.completed or t.description or 'Darbi'),para(f'{amount:.2f}')])
 tab=Table(rows,colWidths=[35,365,115],repeatRows=1)
 tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#173b60')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 vat=D(total*D(o.vat)/100)
 elements.extend([tab,Spacer(1,14),para(f'Kopā bez PVN: {total:.2f} EUR'),para(f'PVN ({o.vat}%): {vat:.2f} EUR'),para(f'Kopā apmaksai: {D(total+vat):.2f} EUR'),Spacer(1,18),para('PROJEKTS — pirms izsniegšanas pārbaudiet rekvizītus, rēķina numuru, apmaksas termiņu un bankas kontu.')])
 doc.build(elements);out.seek(0)
 audit('invoice_draft_pdf',pid,'PN rēķina projekts');g.db.commit()
 return send_file(out,mimetype='application/pdf',as_attachment=True,download_name=f'REKINS_PROJEKTS_PN_{pid}.pdf')
