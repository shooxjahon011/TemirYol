import PyPDF2
import docx
import csv
import openpyxl
from datetime import datetime, timezone
from django.db.models import  Sum
from django.http import HttpResponse,JsonResponse
from django.shortcuts import  redirect,render,get_object_or_404
from django.templatetags.static import static
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from .models import  ChatMessage, WorkSchedule
from datetime import timedelta, date
from my_app.models import UserProfile, IshchiGuruh ,Otryad,UserLocation,LocationHistory
import logging
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import json
import uuid
import math
from django.contrib.auth.hashers import make_password
logger = logging.getLogger(__name__)
def boss_registration(request):
    # Otryad va Guruhlarni bazadan olish
    otryadlar = Otryad.objects.all()
    guruhlar = IshchiGuruh.objects.all()

    if request.method == "POST":
        f_name = request.POST.get('f_name', '').strip()
        l_name = request.POST.get('l_name', '').strip()
        u_login = request.POST.get('u_login')
        u_pass = request.POST.get('u_pass')
        u_phone = request.POST.get('phone')
        u_otryad_id = request.POST.get('otryad')
        u_guruh_id = request.POST.get('guruh')

        # Manzil ma'lumotlari
        viloyat = request.POST.get('viloyat')
        tuman = request.POST.get('tuman')
        mahalla = request.POST.get('mahalla')
        kocha = request.POST.get('kocha')
        uy = request.POST.get('uy')

        unique_tabel_raqami = f"BOSHLIQ-{u_login}-{uuid.uuid4().hex[:4].upper()}"

        try:
            UserProfile.objects.create(
                full_name=f"{f_name} {l_name}",
                login=u_login,
                password=make_password(u_pass),
                phone=u_phone,
                tabel_raqami=unique_tabel_raqami,
                otryad_id=u_otryad_id if u_otryad_id else None,
                guruh_id=u_guruh_id if u_guruh_id else None,
                viloyat=viloyat,
                shahar_tuman=tuman,
                mahalla=mahalla,
                kocha=kocha,
                uy_raqami=uy,
                is_boss=True,
                is_active=True
            )
            return redirect('/')
        except Exception as e:
            return HttpResponse(f"Xatolik yuz berdi: {e}")

    # Template-ga ma'lumotlarni yuborish
    context = {
        'otryadlar': otryadlar,
        'guruhlar': guruhlar
    }
    return render(request, 'boss_registration.html', context)
def baxtsiz_hodisa(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    user = UserProfile.objects.filter(login=user_login).first()
    is_boss = getattr(user, 'is_boss', False)
    video_url = static('uzb.mp4')

    if request.method == "POST" and is_boss:
        fayl = request.FILES.get('admin_file')
        text_input = request.POST.get('text', '')
        final_content = text_input + "\n"

        if fayl:
            ext = fayl.name.split('.')[-1].lower()
            try:
                if ext == 'pdf':
                    reader = PyPDF2.PdfReader(fayl)
                    for page in reader.pages: final_content += page.extract_text() + "\n"
                elif ext in ['doc', 'docx']:
                    doc = docx.Document(fayl)
                    for para in doc.paragraphs: final_content += para.text + "\n"
                elif ext in ['xls', 'xlsx']:
                    wb = openpyxl.load_workbook(fayl, data_only=True)
                    for row in wb.active.iter_rows(values_only=True):
                        final_content += " | ".join([str(c) for c in row if c]) + "\n"
            except Exception as e:
                return HttpResponse(f"Fayl tahlilida xatolik: {e}")

        if final_content.strip():
            ChatMessage.objects.create(
                user=user,
                text=f"🔴 DIQQAT! BAXTSIZ HODISA XABARI:\nYubordi: {user.full_name or user.login}\n{final_content}"
            )
        return redirect('/Baxtsizhodisalar/')

    # Ma'lumotlarni yig'ish
    messages = ChatMessage.objects.filter(text__contains="DIQQAT! BAXTSIZ HODISA").order_by('-created_at')

    formatted_messages = []
    for m in messages:
        formatted_messages.append({
            'time': timezone.localtime(m.created_at).strftime('%H:%M | %d.%m.%Y'),
            'text': m.text.replace("🔴 DIQQAT! BAXTSIZ HODISA XABARI:", "").strip()
        })

    context = {
        'is_boss': is_boss,
        'video_url': video_url,
        'messages': formatted_messages,
    }
    return render(request, 'baxtsiz_hodisa.html', context)
def update_status(request):
    user_login = request.session.get('user_login')
    if user_login:
        UserProfile.objects.filter(login=user_login).update(last_seen=timezone.now())
        return HttpResponse("OK")
    return HttpResponse("Unauthorized", status=401)
def hisoblash_view(request):
    # GET ma'lumotlarini olish
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    user_okladi_str = request.GET.get('oklad')
    korsatkich_str = request.GET.get('korsatkich')

    context = {
        'video_url': static('uzb.mp4'),
        'start_date_str': start_date_str,
        'end_date_str': end_date_str,
        'user_okladi_str': user_okladi_str,
        'korsatkich_str': korsatkich_str,
        'result': None,
        'error': None
    }

    if start_date_str and end_date_str and user_okladi_str and korsatkich_str:
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            user_okladi = float(user_okladi_str)
            korsatkich = float(korsatkich_str)

            if start > end:
                context['error'] = "Sana noto'g'ri kiritildi!"
            else:
                count_yakshanba = 0
                total_days = 0
                current_date = start
                while current_date <= end:
                    total_days += 1
                    if current_date.weekday() == 6:
                        count_yakshanba += 1
                    current_date += timedelta(days=1)

                ish_kunlari = total_days - count_yakshanba
                foiz = 50 if korsatkich <= 20 else 75
                hisob_uchun_asos = user_okladi * (foiz / 100)
                KUNLIK_STAVKA = 100000
                ish_kunlari_uchun_haq = ish_kunlari * KUNLIK_STAVKA
                jami_summa = hisob_uchun_asos + ish_kunlari_uchun_haq

                context['result'] = {
                    'oklad': user_okladi,
                    'foiz': foiz,
                    'asos': hisob_uchun_asos,
                    'kunlar': ish_kunlari,
                    'kunlik_stavka': KUNLIK_STAVKA,
                    'kunlik_haq': ish_kunlari_uchun_haq,
                    'jami': jami_summa
                }
        except ValueError:
            context['error'] = "Ma'lumotlarni kiritishda xatolik!"

    return render(request, 'hisoblash.html', context)
def get_safe_razryad(user):
    try:
        if not user or not user.razryad:
            return 0
        r_str = str(user.razryad).strip()
        if "/" in r_str:
            num, den = r_str.split("/")
            return float(num) / float(den)
        return float(r_str)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
def salary_menu_view(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    user = UserProfile.objects.filter(login=user_login).first()
    if not user:
        return redirect('/')

    # Razryadni tekshirish logikasi
    # get_safe_razryad funksiyasi mavjud deb hisoblaymiz
    current_razryad = get_safe_razryad(user)

    if current_razryad >= (5 / 3):
        auto_url = "/Conculator/"
    else:
        auto_url = "/Kankulyator_Auto/"

    context = {
        'user': user,
        'auto_url': auto_url,
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'salary_menu.html', context)
def common_calculator_logic(request, bonus_rate, check_type):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    # Formadan kelayotgan ma'lumotlar
    salary = request.GET.get('salary')
    norma_soat = request.GET.get('norma_soat')
    ishlangan_soat = request.GET.get('ishlangan_soat')
    tungi_soat = request.GET.get('tungi_soat', '0')
    bayram_soati = request.GET.get('bayram_soati', '0')

    context = {
        'salary': salary,
        'norma_soat': norma_soat,
        'ishlangan_soat': ishlangan_soat,
        'tungi_soat': tungi_soat,
        'bayram_soati': bayram_soati,
        'video_url': static('uzb.mp4'),
        'netto': None,
        'error': None
    }

    if salary and norma_soat and ishlangan_soat:
        try:
            s = float(salary)
            n_s = float(norma_soat)
            i_s = float(ishlangan_soat)
            t_s = float(tungi_soat or 0)
            b_s = float(bayram_soati or 0)

            # Bir soatlik ish haqi
            m = s / n_s

            # Brutto hisoblash formulasi
            # (m * i_s) -> oylik
            # (m * i_s * bonus_rate) -> bonus (50% yoki 75%)
            # (t_s * m * 0.5) -> tungi soat ustamasi
            # ((490000 / n_s) * i_s) -> ovqatlanish puli (misol)
            # (b_s * m) -> bayram soati uchun 100% ustama
            brutto = (m * i_s) + (m * i_s * bonus_rate) + (t_s * m * 0.5) + ((490000 / n_s) * i_s) + (b_s * m)

            # Soliqlarni chegirish (13.1%)
            soliq = brutto * 0.131
            context['netto'] = brutto - soliq

        except (ValueError, ZeroDivisionError):
            context['error'] = "Ma'lumotlarni kiritishda xatolik yuz berdi!"

    return render(request, 'calculator_base.html', context)
def salary_calc_manual_view(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    # Formadan kelayotgan ma'lumotlar
    salary = request.GET.get('salary')
    norma_soat = request.GET.get('norma_soat')
    ishlangan_soat = request.GET.get('ishlangan_soat')
    bonus_percent = request.GET.get('bonus_percent')
    tungi_soat = request.GET.get('tungi_soat', '0')
    bayram_soati = request.GET.get('bayram_soati', '0')

    context = {
        'salary': salary,
        'norma_soat': norma_soat,
        'ishlangan_soat': ishlangan_soat,
        'bonus_percent': bonus_percent,
        'tungi_soat': tungi_soat,
        'bayram_soati': bayram_soati,
        'video_url': static('uzb.mp4'),
        'netto': None,
        'error': None
    }

    if salary and norma_soat and ishlangan_soat and bonus_percent:
        try:
            s = float(salary)
            n = float(norma_soat)
            i = float(ishlangan_soat)
            bp = float(bonus_percent) / 100
            ts = float(tungi_soat or 0)
            bs = float(bayram_soati or 0)

            # Bir soatlik stavka
            m = s / n

            # Brutto: Oylik + Mukofot + Tungi + Ovqatlanish + Bayram
            brutto = (m * i) + (m * i * bp) + (ts * m * 0.5) + ((490000 / n) * i) + (bs * m)

            # 13.1% Soliqni chegirish
            context['netto'] = brutto - (brutto * 0.131)

        except (ValueError, ZeroDivisionError):
            context['error'] = "Ma'lumotlarda xatolik yuz berdi!"

    return render(request, 'calculator_manual.html', context)
def render_page(request, rate, s, n, i, ts, bs, netto=None, error=None, is_manual=False, bonus_percent=""):
    # Dinamik sarlavha va ranglarni aniqlash
    title = "QO'LDA KIRITISH" if is_manual else f"{int(rate * 100)}% KALKULYATOR"
    color = "#ff9d00" if is_manual else "#00f2ff"

    context = {
        'title': title,
        'color': color,
        'is_manual': is_manual,
        'salary': s,
        'norma_soat': n,
        'ishlangan_soat': i,
        'bonus_percent': bonus_percent,
        'tungi_soat': ts,
        'bayram_soati': bs,
        'netto': netto,
        'error': error,
        'video_url': static('uzb.mp4'),  # Video fon uchun
    }

    return render(request, 'calculator_template.html', context)
def salary_calc_view(request):
    return common_calculator_logic(request, 0.20, "high")
def salary_calc_view1(request):
    return common_calculator_logic(request, 0.40, "low")
def boss_reports(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    # Boss profilini tekshirish
    boss = UserProfile.objects.filter(login=user_login).first()
    if not boss or not boss.is_boss:
        return redirect('/second/')

    # Bossning otryadidagi ishchilarni filtrlash
    workers = UserProfile.objects.filter(otryad=boss.otryad, is_boss=False)

    context = {
        'boss': boss,
        'workers': workers,
        'video_url': static('uzb.mp4'),
    }

    return render(request, 'boss_reports.html', context)
def add_report_for_worker(request, worker_id):
    # Foydalanuvchi va Boss tekshiruvi
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    boss = UserProfile.objects.filter(login=user_login).first()
    if not boss or not boss.is_boss:
        return redirect('/second/')

    # Ishchini topamiz
    worker = get_object_or_404(UserProfile, id=worker_id)

    if request.method == "POST":
        try:
            # Formadan ma'lumotlarni olish
            WorkSchedule.objects.create(
                user=worker,
                date=request.POST.get('sana'),
                oklad=request.POST.get('oklad'),
                norma_soati=request.POST.get('norma'),
                ishlagan_soati=request.POST.get('ishlagan'),
                tungi_soati=request.POST.get('tungi', 0) or 0,
                bayram_soati=request.POST.get('bayram', 0) or 0
            )
            return redirect(f'/boss/worker-report/{worker.id}/')
        except Exception as e:
            # Xatolikni template orqali ko'rsatish tavsiya etiladi
            return render(request, 'add_report.html', {'worker': worker, 'error': str(e)})

    context = {
        'worker': worker,
        'today_date': timezone.now().strftime('%Y-%m-%d'),
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'add_report.html', context)
def second_view(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    user = UserProfile.objects.filter(login=user_login).first()
    if not user or not user.is_active:
        request.session.flush()
        return redirect('/login/')

    # Boss bo'lsa rahbarlar sahifasiga o'tkazish
    if getattr(user, 'is_boss', False):
        return redirect('/bosspage/')

    # 24 soatdan ortiq ishlagan bo'lsa avtomatik to'xtatish
    is_working = getattr(user, 'is_working', False)
    if is_working and user.work_start_time:
        diff = timezone.now() - user.work_start_time
        if diff.total_seconds() >= 86400:
            user.is_working = False
            user.save()
            is_working = False

    # Resurslar va ma'lumotlar
    avatar_url = user.image.url if user.image else static('default_avatar.png')

    context = {
        'user': user,
        'display_name': user.full_name or user.login,
        'avatar_url': avatar_url,
        'is_working': is_working,
        'video_url': static('uzb.mp4'),
        'csrf_token': get_token(request),
        # Tugma holati uchun
        'btn_text': "Ishni tugatdim" if is_working else "Men ishga keldim",
        'btn_class': "btn-working" if is_working else "btn-idle",
    }

    return render(request, 'main_menu.html', context)
def profile_view(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    user = UserProfile.objects.filter(login=user_login).first()
    if not user:
        return redirect('/')

    # Ma'lumotlarni yangilash
    if request.method == "POST":
        new_name = request.POST.get('display_name')
        new_pic = request.FILES.get('profile_pic')

        if new_name:
            user.login = new_name
        if new_pic:
            user.image = new_pic

        user.save()
        request.session['user_login'] = user.login
        return redirect('/profile/')

    context = {
        'user': user,
        'avatar_url': user.image.url if user.image else static('default_avatar.png'),
        'video_url': static('uzb.mp4'),
        'user_razryad': getattr(user, 'razryad', 'Kiritilmagan'),
    }

    return render(request, 'profile.html', context)
def chats(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    current_user = UserProfile.objects.filter(login=user_login).first()
    if not current_user:
        return redirect('/')

    # Har kirganda foydalanuvchi faolligini yangilash
    current_user.last_seen = timezone.now()
    current_user.save(update_fields=['last_seen'])

    user_guruh = current_user.guruh

    # 1. POST so'rovlarini qayta ishlash
    if request.method == "POST":
        delete_id = request.POST.get('delete_id')
        if delete_id:
            ChatMessage.objects.filter(id=delete_id, user=current_user).delete()
            return HttpResponse("OK")

        text = request.POST.get('text')
        image = request.FILES.get('image')
        video = request.FILES.get('video')
        voice = request.FILES.get('voice')

        if text or image or video or voice:
            ChatMessage.objects.create(
                user=current_user,
                guruh=user_guruh,
                text=text, image=image, video=video, voice=voice
            )
            return HttpResponse("OK")

    # 2. Xabarlar ro'yxatini yig'ish (Update uchun)
    all_messages = ChatMessage.objects.filter(guruh=user_guruh).order_by('created_at')

    if request.GET.get('update'):
        # Faqat xabarlar qismini render qilamiz
        return render(request, 'chat_messages_partial.html', {'messages': all_messages, 'user_login': user_login})

    # 3. Asosiy sahifa yuklanishi
    besh_daqiqa_oldin = timezone.now() - timezone.timedelta(minutes=5)
    is_online = current_user.last_seen > besh_daqiqa_oldin
    status_text = "online" if is_online else f"oxirgi marta: {timezone.localtime(current_user.last_seen).strftime('%H:%M')}"

    context = {
        'messages': all_messages,
        'user_login': user_login,
        'header_title': f"{user_guruh.nomi} Guruhi" if user_guruh else "Chat",
        'status_text': status_text,
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'chat_main.html', context)
def logout_view(request):
    request.session.flush()
    return redirect('../') # Login sahifasiga qaytarish
def delete_message(request, msg_id):
    if request.method == "POST":
        msg = ChatMessage.objects.filter(id=msg_id).first()
        # Faqat o'z xabarini yoki admin o'chira olishi uchun:
        user_login = request.session.get('user_login')
        if msg and msg.user.login == user_login:
            msg.delete()
            return HttpResponse("OK")
    return HttpResponse("Xato", status=400)
def login_view(request):
    error_message = ""

    if request.method == "POST":
        u = request.POST.get('u_name', '').strip()
        p = request.POST.get('p_val', '').strip()

        # Maxsus kirish kodi
        if u == "1" and p == "1":
            return redirect('/boss-registration/')

        user = UserProfile.objects.filter(login__iexact=u).first()

        if not user:
            error_message = f'"{u}" logini topilmadi!'
        elif user.password != p:
            error_message = "Parol noto'g'ri!"
        else:
            request.session['user_login'] = user.login
            return redirect('/second/')

    context = {
        'error_message': error_message,
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'login.html', context)
def signup(request):
    if request.method == "POST":
        u = request.POST.get('u_name')
        p = request.POST.get('p_val')
        tel = request.POST.get('tel_val')
        tabel = request.POST.get('t_raqam')
        fname = request.POST.get('full_name')
        raz_val = request.POST.get('razryad')
        guruh_id = request.POST.get('guruh_id')
        otryad_id = request.POST.get('otryad_id')

        tariflar = {"5/3": 5336929, "5/2": 4800000, "4/3": 4100000}
        oklad_val = tariflar.get(raz_val, 0)

        if UserProfile.objects.filter(login=u).exists():
            return render(request, 'signup.html', {'error': 'Bu login band!', 'otryadlar': Otryad.objects.all()})

        if all([u, p, tel, guruh_id, otryad_id]):
            try:
                otryad_obj = Otryad.objects.get(id=int(otryad_id))
                guruh_obj = IshchiGuruh.objects.get(id=int(guruh_id))

                yangi_user = UserProfile(
                    login=u, password=p, phone=tel,
                    tabel_raqami=tabel, full_name=fname,
                    razryad=raz_val, oklad=oklad_val,
                    is_active=False,
                    otryad=otryad_obj,
                    guruh=guruh_obj
                )
                yangi_user.save()
                return redirect(f'/verify-code/?login={u}')
            except Exception as e:
                return render(request, 'signup.html', {'error': f'Xatolik: {e}', 'otryadlar': Otryad.objects.all()})
        else:
            return render(request, 'signup.html',
                          {'error': 'Barcha maydonlarni to\'ldiring!', 'otryadlar': Otryad.objects.all()})

    # GET so'rovi uchun ma'lumotlar
    otryadlar = Otryad.objects.all()
    guruhlar = IshchiGuruh.objects.all()

    guruhlar_dict = {}
    for g in guruhlar:
        if g.otryad_id not in guruhlar_dict:
            guruhlar_dict[g.otryad_id] = []
        guruhlar_dict[g.otryad_id].append({'id': g.id, 'nomi': g.nomi})

    context = {
        'otryadlar': otryadlar,
        'guruhlar_json': json.dumps(guruhlar_dict),
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'signup.html', context)
def verify_code_view(request):
    # GET yoki POST orqali kelgan loginni olish
    login_val = request.GET.get('login') or request.POST.get('login')
    user = UserProfile.objects.filter(login=login_val).first()

    if not user:
        return redirect('/')

    if request.method == "POST":
        entered_code = request.POST.get('activation_code')

        if user.activation_code == entered_code:
            user.is_active = True
            user.save()
            request.session['user_login'] = user.login
            return redirect('/second/')
        else:
            # Xato kod kiritilganda sahifani xato xabari bilan qaytaramiz
            return render(request, 'verify_code.html', {
                'error': "Xato kod kiritildi!",
                'login_val': login_val,
                'video_url': static('uzb.mp4')
            })

    context = {
        'login_val': login_val,
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'verify_code.html', context)
def hisobot(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/')

    current_user = UserProfile.objects.filter(login=user_login).first()
    if not current_user:
        return redirect('/')

    # Jadval ma'lumotlarini olish
    jadval_malumotlari = WorkSchedule.objects.filter(user=current_user).order_by('-date')

    # Jami yig'indilarni hisoblash
    jami = jadval_malumotlari.aggregate(
        t_ish=Sum('ishlagan_soati'),
        t_tungi=Sum('tungi_soati'),
        t_bayram=Sum('bayram_soati')
    )

    # Oxirgi kiritilgan norma va okladni olish (jami qatori uchun)
    last_entry = jadval_malumotlari.first()

    context = {
        'current_user': current_user,
        'jadval': jadval_malumotlari,
        'jami': jami,
        'last_entry': last_entry,
        'video_url': static('uzb.mp4'),
    }

    return render(request, 'hisobot.html', context)
def boss(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    user = UserProfile.objects.filter(login=user_login).first()

    # Boss ekanligini tekshirish
    if not user or not user.is_boss:
        return redirect('/second/')

    # Aktiv ishchilar sonini hisoblash (Jonli kuzatuv uchun)
    active_workers_count = UserLocation.objects.filter(is_active=True).count()

    context = {
        'display_name': user.full_name or user.login,
        'avatar_url': user.image.url if user.image else static('default_avatar.png'),
        'guruh_nomi': user.otryad.nomi if user.otryad else "Bo'lim tayinlanmagan",
        'active_workers_count': active_workers_count,
        'video_url': static('uzb.mp4'),
    }
    return render(request, 'boss_panel.html', context)
def active_workers_list(request):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    user = UserProfile.objects.filter(login=user_login).first()
    if not user or not user.is_boss:
        return redirect('/second/')

    # Aktiv ishchilarni barcha kerakli bog'liqliklar (select_related) bilan olish
    active_locations = UserLocation.objects.filter(is_active=True).select_related('user')

    context = {
        'active_locations': active_locations,
        'count': active_locations.count(),
        'default_avatar': static('default_avatar.png'),
    }
    return render(request, 'active_workers.html', context)
def track_worker(request, worker_id):
    user_login = request.session.get('user_login')
    if not user_login:
        return redirect('/login/')

    # Ishchini bazadan olish
    worker = get_object_or_404(UserProfile, id=worker_id)

    # Boshlang'ich kordinatalarni olish
    last_loc = UserLocation.objects.filter(user=worker).first()

    context = {
        'worker': worker,
        'display_name': worker.full_name or worker.login,
        'start_lat': last_loc.latitude if last_loc else 41.3111,
        'start_lng': last_loc.longitude if last_loc else 69.2797,
    }
    return render(request, 'track_worker.html', context)
def get_worker_location(request, worker_id):
    worker = get_object_or_404(UserProfile, id=worker_id)
    try:
        loc = UserLocation.objects.get(user=worker)
        return JsonResponse({
            'lat': loc.latitude,
            'lng': loc.longitude,
            'is_active': loc.is_active
        })
    except UserLocation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
@csrf_exempt
def toggle_work(request):
    if request.method == "POST":
        user_login = request.session.get('user_login')

        if not user_login:
            return JsonResponse({"status": "error", "message": "Foydalanuvchi topilmadi"}, status=403)

        user = get_object_or_404(UserProfile, login=user_login)
        action = request.POST.get('action')

        # 1. UserProfile modelidagi is_working ni yangilash
        if action == 'start':
            user.is_working = True
            user.work_start_time = timezone.now()
            logger.info(f"User {user.login} started work.")

        elif action == 'stop':
            user.is_working = False
            logger.info(f"User {user.login} stopped work.")

        user.save()

        # 2. UserLocation modelidagi is_active ni yangilash
        # get_or_create xatolik bermasligi uchun standart qiymatlar beramiz
        user_loc, created = UserLocation.objects.get_or_create(
            user=user,
            defaults={
                'latitude': 0.0,  # Standart qiymat
                'longitude': 0.0,  # Standart qiymat
                'is_active': False
            }
        )

        user_loc.is_active = (action == 'start')
        # Agar 'start' bo'lsa va latitude 0 bo'lsa, uni haqiqiy GPS bilan
        # update_location funksiyasida yangilashni kuting.
        user_loc.save()

        return JsonResponse({"status": "success", "is_working": user.is_working})

    return JsonResponse({"status": "error", "message": "Faqat POST so'rovi qabul qilinadi"}, status=405)@csrf_exempt  # GPS so'rovlari API orqali kelgani uchun CSRF tekshiruvini o'chiramiz
def update_location(request):
    """
    Ishchining joriy joylashuvini yangilaydi
    """
    if request.method == "POST":
        # Foydalanuvchini sessiyadan olish
        user_login = request.session.get('user_login')

        if not user_login:
            return JsonResponse({"status": "error", "message": "Foydalanuvchi topilmadi"}, status=403)

        # Foydalanuvchi obyektini bazadan olish
        user = get_object_or_404(UserProfile, login=user_login)

        # Koordinatalarni olish
        lat = request.POST.get('lat')
        lng = request.POST.get('lng')

        if not lat or not lng:
            return JsonResponse({"status": "error", "message": "Koordinatalar yo'q"}, status=400)

        # 1. Joriy joylashuvni yangilash (yoki yaratish)
        user_loc, created = UserLocation.objects.get_or_create(user=user)
        user_loc.latitude = lat
        user_loc.longitude = lng
        user_loc.last_updated = timezone.now()
        user_loc.is_active = True  # GPS ma'lumot kelayotgan bo'lsa, demak ishda
        user_loc.save()

        # 2. Tarixga yozish (LocationHistory modelida tarix bo'lsa)
        LocationHistory.objects.create(
            user=user,
            latitude=lat,
            longitude=lng
        )

        logger.info(f"Updated location for {user.login}: {lat}, {lng}")

        return JsonResponse({"status": "success", "message": "Joylashuv yangilandi"})

    return JsonResponse({"status": "error", "message": "Faqat POST so'rovi qabul qilinadi"}, status=405)
