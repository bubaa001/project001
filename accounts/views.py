import random #ili tupate random quiz choices
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.db import models
from .forms import RegisterForm, LoginForm
from .models import User, AcademicClass, Module, ClassContent, ArchiveCategory, ArchiveItem, Quiz, Question, Choice, StudentQuizSubmission, LibraryBook, InstructorProfile
from sync_manager.triggers import trigger_sync_after_action



# HELPER: XP Tier System


def get_tier_info(xp):
    """Return (level, tier_title, range_min, range_max) for a given XP value."""
    if xp < 500:
        return (1, 'Initiate', 0, 500)
    elif xp < 1500:
        return (2, 'Scholar', 500, 1500)
    elif xp < 3000:
        return (3, 'Alpha Vanguard', 1500, 3000)
    elif xp < 5000:
        return (4, 'Elite Scholar', 3000, 5000)
    else:
        level = 5 + (xp - 5000) // 3000
        rmin = 5000 + ((xp - 5000) // 3000) * 3000
        rmax = rmin + 3000
        return (level, 'Grandmaster', rmin, rmax)


def build_xp_context(current_xp):
    """Build XP progress context dict from a raw XP value."""
    base_level, tier_title, level_range_min, level_range_max = get_tier_info(current_xp)
    total_in_tier = level_range_max - level_range_min
    progress_in_tier = current_xp - level_range_min
    xp_percentage = int((progress_in_tier / total_in_tier) * 100) if total_in_tier > 0 else 100
    xp_to_next = max(0, level_range_max - current_xp)
    return {
        'current_level': base_level,
        'tier_title': tier_title,
        'xp_percentage': min(100, max(0, xp_percentage)),
        'xp_to_next': xp_to_next,
    }


# HELPER: Quiz Question Results Builder


def build_question_results(submission, questions):
    """Build a list of question result dicts from a submission and its questions."""
    results = []
    for question in questions:
        selected_choice_id = submission.answers.get(str(question.id))
        selected_choice = None
        correct_choice = None
        is_correct = False
        for choice in question.choices.all():
            if choice.is_correct:
                correct_choice = choice
            if selected_choice_id and choice.id == selected_choice_id:
                selected_choice = choice
                is_correct = choice.is_correct
        results.append({
            'question': question,
            'selected_choice': selected_choice,
            'correct_choice': correct_choice,
            'is_correct': is_correct,
        })
    return results



# HELPER: Leaderboard Data


def get_leaderboard_data(request):
    """Build leaderboard context: top 5 students, current user rank, tier list."""
    students = User.objects.filter(role='student').order_by('-xp')

    # Top 5 leaderboard
    top5 = []
    for i, s in enumerate(students[:5], start=1):
        level, title, _, _ = get_tier_info(s.xp or 0)
        top5.append({
            'rank': i,
            'username': s.username,
            'xp': s.xp or 0,
            'level': level,
            'title': title,
        })

    # Current user's rank and info
    current_user_rank = None
    xp_gap_to_top = None
    current_user_tier = None
    if request.user.is_authenticated and request.user.role == 'student':
        for i, s in enumerate(students, start=1):
            if s.id == request.user.id:
                current_user_rank = i
                break
        if top5:
            top_xp = top5[0]['xp']
            xp_gap_to_top = max(0, top_xp - (request.user.xp or 0))
        _, current_user_tier, _, _ = get_tier_info(request.user.xp or 0)

    # All tiers definition
    tiers = [
        {'level': 1, 'title': 'Initiate', 'range_min': 0, 'range_max': 500, 'description': 'The beginning of the journey'},
        {'level': 2, 'title': 'Scholar', 'range_min': 500, 'range_max': 1500, 'description': 'Dedicated to the pursuit of knowledge'},
        {'level': 3, 'title': 'Alpha Vanguard', 'range_min': 1500, 'range_max': 3000, 'description': 'Leading the charge in intellectual warfare'},
        {'level': 4, 'title': 'Elite Scholar', 'range_min': 3000, 'range_max': 5000, 'description': 'Among the finest minds in the arena'},
        {'level': 5, 'title': 'Grandmaster', 'range_min': 5000, 'range_max': None, 'description': 'The pinnacle of scholarly dominance'},
    ]

    user_xp = request.user.xp if request.user.is_authenticated else 0
    for tier in tiers:
        tier['is_unlocked'] = user_xp >= tier['range_min']
        if tier['range_max'] is None:
            tier['progress_pct'] = 100 if tier['is_unlocked'] else 0
        else:
            tier_range = tier['range_max'] - tier['range_min']
            clamped = max(0, min(tier['range_max'], user_xp) - tier['range_min'])
            tier['progress_pct'] = int((clamped / tier_range) * 100) if tier_range > 0 else 0

    return {
        'top5_leaderboard': top5,
        'current_user_rank': current_user_rank,
        'xp_gap_to_top': xp_gap_to_top,
        'current_user_tier': current_user_tier,
        'tiers': tiers,
        'total_students': students.count(),
    }



# VIEWS: Core / Auth


def home_view(request):
    student_count = User.objects.filter(role='student').count()
    instructor_count = User.objects.filter(role='instructor').count()
    class_count = AcademicClass.objects.count()

    top_student = User.objects.filter(role='student').order_by('-xp').first()
    top_student_name = "NO SCHOLARS YET"
    top_student_xp = 0
    active_title = "Initiate"
    if top_student:
        top_student_name = top_student.username.upper()
        top_student_xp = top_student.xp
        _, active_title, _, _ = get_tier_info(top_student_xp or 0)

    return render(request, 'home.html', {
        'student_count': student_count,
        'instructor_count': instructor_count,
        'class_count': class_count,
        'top_student_name': top_student_name,
        'top_student_xp': top_student_xp,
        'active_title': active_title,
    })


@ensure_csrf_cookie
def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            trigger_sync_after_action()  # immediate sync attempt for new account
            if user.role == 'student':
                return redirect('select_level')
            elif user.role == 'instructor':
                return redirect('pending_approval')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


@ensure_csrf_cookie
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.role == 'student':
                return redirect('study_dashboard')
            elif user.role == 'instructor':
                return redirect('instructor_dashboard' if user.is_approved else 'pending_approval')
            elif user.role == 'admin' or user.is_superuser:
                return redirect('admin_dashboard')
    else:
        form = LoginForm(request)
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')



# VIEWS: Student


def select_level_view(request):
    """Show all classes that have an instructor assigned, for students to enroll."""
    classes = AcademicClass.objects.filter(instructor__isnull=False)
    enrolled_class_ids = []
    if request.user.is_authenticated:
        enrolled_class_ids = list(request.user.enrolled_classes.values_list('id', flat=True))

    if request.method == 'POST' and request.user.is_authenticated:
        class_id = request.POST.get('class_id')
        action = request.POST.get('action')
        if class_id and action == 'enroll':
            academic_class = get_object_or_404(AcademicClass, id=class_id)
            if request.user not in academic_class.students.all():
                academic_class.students.add(request.user)
            return redirect('study_dashboard')
        elif class_id and action == 'unenroll':
            academic_class = get_object_or_404(AcademicClass, id=class_id)
            academic_class.students.remove(request.user)
            return redirect('select_level')

    return render(request, 'select_level.html', {
        'classes': classes,
        'enrolled_class_ids': enrolled_class_ids,
    })


@login_required
def student_dashboard_view(request):
    user = request.user
    current_xp = user.xp if hasattr(user, 'xp') else 0
    xp_context = build_xp_context(current_xp)

    academic_status = {
        'semester_label': 'Spring Semester',
        'current_week': '08',
        **xp_context,
    }

    return render(request, 'student_dashboard.html', {
        'current_student': user,
        'academic_status': academic_status,
        'enrolled_classes': AcademicClass.objects.filter(students=user),
    })


@login_required
def student_class_view(request, slug):
    """Student views a class they're enrolled in, sees content and quizzes grouped by module."""
    academic_class = get_object_or_404(AcademicClass, slug=slug)
    if request.user not in academic_class.students.all() and request.user.role != 'instructor':
        return redirect('study_dashboard')

    quizzes = academic_class.quizzes.all()
    submissions = StudentQuizSubmission.objects.filter(student=request.user, quiz__in=quizzes)
    submission_map = {s.quiz_id: s for s in submissions}

    modules = academic_class.modules.prefetch_related(
        models.Prefetch('contents', queryset=ClassContent.objects.all()),
        models.Prefetch('quizzes', queryset=Quiz.objects.prefetch_related('questions')),
    ).all()

    module_data = []
    for module in modules:
        module_quiz_data = []
        for quiz in module.quizzes.all():
            sub = submission_map.get(quiz.id)
            module_quiz_data.append({
                'quiz': quiz,
                'submission': sub,
                'has_submitted': sub is not None,
            })
        module_data.append({
            'module': module,
            'contents': module.contents.all(),
            'quiz_data': module_quiz_data,
        })

    orphaned_contents = academic_class.contents.filter(module__isnull=True)
    orphaned_quizzes = academic_class.quizzes.filter(module__isnull=True)
    orphaned_quiz_data = [
        {'quiz': quiz, 'submission': submission_map.get(quiz.id), 'has_submitted': submission_map.get(quiz.id) is not None}
        for quiz in orphaned_quizzes
    ]

    return render(request, 'student_class_detail.html', {
        'class': academic_class,
        'module_data': module_data,
        'orphaned_contents': orphaned_contents,
        'orphaned_quiz_data': orphaned_quiz_data,
    })


@login_required
def student_profile_view(request):
    user = request.user if request.user.is_authenticated else None
    student_name = (user.get_full_name() or user.username) if user else 'Student'
    current_xp = user.xp if user and hasattr(user, 'xp') else 0

    _, rank_title, level_range_min, level_range_max = get_tier_info(current_xp)
    xp_percentage = min(100, int(((current_xp - level_range_min) / (level_range_max - level_range_min)) * 100)) if current_xp > 0 else 0

    enrolled_classes = AcademicClass.objects.filter(students=user) if user and user.is_authenticated else []

    return render(request, 'student_profile.html', {
        'student': {
            'full_name': student_name,
            'rank_title': rank_title,
            'xp_percentage': xp_percentage,
        },
        'enrolled_classes': enrolled_classes,
        'enrolled_count': enrolled_classes.count(),
    })



# VIEWS: Instructor


def instructor_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != 'instructor':
        return redirect('home')
    if not request.user.is_approved:
        return redirect('pending_approval')

    return render(request, 'instructor_dashboard.html', {
        'my_classes': AcademicClass.objects.filter(instructor=request.user),
    })


def pending_approval_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role != 'instructor':
        return redirect('home')
    if request.user.is_approved:
        return redirect('instructor_dashboard')
    return render(request, 'pending_approval.html')


@login_required
def instructor_manage_classes_view(request):
    if request.user.role != 'instructor':
        return redirect('home')
    if not request.user.is_approved:
        return redirect('pending_approval')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Handle class creation
        if action == 'create':
            code = request.POST.get('code', '').strip()
            title = request.POST.get('title', '').strip()
            if code and title:
                from django.utils.text import slugify
                slug = slugify(code)
                base_slug = slug
                counter = 1
                while AcademicClass.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                AcademicClass.objects.create(
                    code=code, title=title,
                    schedule_string=request.POST.get('schedule_string', '').strip() or 'TBD',
                    meeting_link=request.POST.get('meeting_link', '').strip(),
                    slug=slug, instructor=request.user,
                )
            return redirect('instructor_manage_classes')

        # Handle assign/remove
        class_id = request.POST.get('class_id')
        if class_id:
            academic_class = get_object_or_404(AcademicClass, id=class_id)
            if action == 'assign' and (academic_class.instructor is None or academic_class.instructor == request.user):
                academic_class.instructor = request.user
                academic_class.save(update_fields=['instructor'])
            elif action == 'remove' and academic_class.instructor == request.user:
                academic_class.instructor = None
                academic_class.save(update_fields=['instructor'])
        return redirect('instructor_manage_classes')

    return render(request, 'instructor_manage_classes.html', {
        'available_classes': AcademicClass.objects.filter(
            models.Q(instructor__isnull=True) | models.Q(instructor=request.user)
        ),
        'my_classes': AcademicClass.objects.filter(instructor=request.user),
    })


@login_required
def instructor_class_view(request, slug):
    """Instructor manages a class: adds modules, content, creates quizzes."""
    if request.user.role != 'instructor':
        return redirect('home')

    academic_class = get_object_or_404(AcademicClass, slug=slug, instructor=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        # Module actions
        if action == 'add_module':
            title = request.POST.get('module_title', '').strip()
            if title:
                last_order = academic_class.modules.aggregate(max_order=models.Max('order'))['max_order'] or 0
                Module.objects.create(academic_class=academic_class, title=title, order=last_order + 1)
            return redirect('instructor_class', slug=slug)

        if action == 'delete_module':
            module_id = request.POST.get('module_id')
            if module_id:
                Module.objects.filter(id=module_id, academic_class=academic_class).delete()
            return redirect('instructor_class', slug=slug)

        # Content actions
        if action == 'add_content':
            title = request.POST.get('title', '').strip()
            if title:
                content = ClassContent.objects.create(
                    academic_class=academic_class, title=title,
                    description=request.POST.get('description', '').strip(),
                )
                module_id = request.POST.get('module_id')
                if module_id:
                    content.module_id = module_id
                    content.save(update_fields=['module_id'])
            return redirect('instructor_class', slug=slug)

        if action == 'delete_content':
            content_id = request.POST.get('content_id')
            if content_id:
                ClassContent.objects.filter(id=content_id, academic_class=academic_class).delete()
            return redirect('instructor_class', slug=slug)

        # Quiz actions
        if action == 'create_quiz':
            title = request.POST.get('quiz_title', '').strip()
            if title:
                quiz = Quiz.objects.create(
                    title=title, description=request.POST.get('quiz_description', '').strip(),
                    creator=request.user, academic_class=academic_class,
                )
                module_id = request.POST.get('module_id')
                if module_id:
                    quiz.module_id = module_id
                    quiz.save(update_fields=['module_id'])

                question_texts = request.POST.getlist('question_text[]')
                for qi, qtext in enumerate(question_texts):
                    if not qtext.strip():
                        continue
                    question = Question.objects.create(quiz=quiz, text=qtext.strip(), order=qi)
                    choice_texts = request.POST.getlist(f'choice_text_{qi}[]')
                    correct_choice = request.POST.get(f'correct_choice_{qi}')
                    has_correct = False
                    for ci, ctext in enumerate(choice_texts):
                        if not ctext.strip():
                            continue
                        is_correct = (str(ci) == correct_choice)
                        if is_correct:
                            has_correct = True
                        Choice.objects.create(question=question, text=ctext.strip(), is_correct=is_correct, order=ci)
                    if not has_correct:
                        first_choice = question.choices.first()
                        if first_choice:
                            first_choice.is_correct = True
                            first_choice.save(update_fields=['is_correct'])
            return redirect('instructor_class', slug=slug)

        if action == 'delete_quiz':
            quiz_id = request.POST.get('quiz_id')
            if quiz_id:
                Quiz.objects.filter(id=quiz_id, academic_class=academic_class).delete()
            return redirect('instructor_class', slug=slug)

    modules = academic_class.modules.prefetch_related(
        models.Prefetch('contents', queryset=ClassContent.objects.all()),
        models.Prefetch('quizzes', queryset=Quiz.objects.prefetch_related('questions__choices', 'submissions')),
    ).all()

    orphaned_contents = academic_class.contents.filter(module__isnull=True)
    orphaned_quizzes = academic_class.quizzes.filter(module__isnull=True)

    # Build student quiz stats
    all_quizzes = list(academic_class.quizzes.all())
    all_submissions = StudentQuizSubmission.objects.filter(quiz__in=all_quizzes).select_related('student')

    student_stats = {}
    for student in academic_class.students.all():
        student_stats[student.id] = {
            'student': student, 'total_quizzes': len(all_quizzes),
            'completed_quizzes': 0, 'total_score': 0, 'total_possible': 0, 'submissions': [],
        }
    for sub in all_submissions:
        if sub.student_id in student_stats:
            stats = student_stats[sub.student_id]
            stats['completed_quizzes'] += 1
            stats['total_score'] += sub.score
            stats['total_possible'] += sub.total
            stats['submissions'].append(sub)

    student_list = sorted(student_stats.values(), key=lambda s: (-s['completed_quizzes'], -s['total_score'] if s['total_possible'] > 0 else 0))

    return render(request, 'instructor_class_detail.html', {
        'class': academic_class, 'modules': modules,
        'orphaned_contents': orphaned_contents, 'orphaned_quizzes': orphaned_quizzes,
        'student_list': student_list,
    })



# VIEWS: Instructor Profile


@login_required
def teacher_profile_view(request, username=None):
    """View an instructor's profile."""
    if username:
        instructor = get_object_or_404(User, username=username, role='instructor')
        profile = InstructorProfile.objects.filter(user=instructor).first()
        if not profile or not profile.has_profile():
            return render(request, 'teacher_profile.html', {
                'profile': None, 'instructor_user': instructor,
                'active_cohorts': [], 'is_own_profile': request.user == instructor,
            })
        taught_classes = AcademicClass.objects.filter(instructor=instructor)
    else:
        if request.user.role != 'instructor':
            return redirect('home')
        instructor = request.user
        profile = InstructorProfile.objects.filter(user=instructor).first()
        if not profile or not profile.has_profile():
            return redirect('edit_instructor_profile')
        taught_classes = AcademicClass.objects.filter(instructor=instructor)

    active_cohorts = [
        {
            'access_level': 'FULL ACCESS',
            'name': cls.title,
            'description': f"{cls.code} — {cls.schedule_string} | Meeting: {cls.meeting_link}",
            'member_count': cls.students.count(),
        }
        for cls in taught_classes
    ]

    return render(request, 'teacher_profile.html', {
        'profile': profile, 'instructor_user': instructor,
        'active_cohorts': active_cohorts, 'is_own_profile': request.user == instructor,
    })


@login_required
def edit_instructor_profile_view(request):
    """Create or edit an instructor's profile."""
    if request.user.role != 'instructor':
        return redirect('home')

    profile, _ = InstructorProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.title_role = request.POST.get('title_role', '').strip()
        profile.bio = request.POST.get('bio', '').strip()
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        established = request.POST.get('established_year', '').strip()
        if established:
            profile.established_year = int(established)

        # Process academic focus (JSON)
        focus_titles = request.POST.getlist('focus_title[]')
        focus_descriptions = request.POST.getlist('focus_description[]')
        profile.academic_focus = [
            {'title': t.strip(), 'description': focus_descriptions[i].strip() if i < len(focus_descriptions) else ''}
            for i, t in enumerate(focus_titles) if t.strip()
        ]

        # Process methodologies (JSON)
        profile.methodologies = [{'name': n.strip()} for n in request.POST.getlist('method_name[]') if n.strip()]

        # Process manuscripts (JSON)
        manuscript_years = request.POST.getlist('manuscript_year[]')
        manuscript_titles = request.POST.getlist('manuscript_title[]')
        manuscript_tags = request.POST.getlist('manuscript_tag[]')
        profile.manuscripts = [
            {
                'publication_year': int(manuscript_years[i]) if i < len(manuscript_years) and manuscript_years[i].strip() else 2024,
                'title': t.strip(),
                'publisher_tag': manuscript_tags[i].strip() if i < len(manuscript_tags) else '',
            }
            for i, t in enumerate(manuscript_titles) if t.strip()
        ]

        profile.save()
        return redirect('teacher_profile')

    return render(request, 'edit_instructor_profile.html', {'profile': profile})


# VIEWS: Admin


@login_required
def admin_dashboard_view(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return HttpResponseForbidden('Not authorized')

    return render(request, 'admin_approval.html', {
        'pending_instructors': User.objects.filter(role='instructor', is_approved=False),
        'approved_instructors': User.objects.filter(role='instructor', is_approved=True),
    })


@login_required
def toggle_instructor_approval_view(request, user_id, approve=True):
    """Approve or disapprove an instructor."""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return HttpResponseForbidden('Not authorized')
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')

    instructor = get_object_or_404(User, pk=user_id, role='instructor')
    instructor.is_approved = approve
    instructor.save(update_fields=['is_approved'])
    return JsonResponse({'status': 'approved' if approve else 'disapproved'})



# VIEWS: Archive / Library


def archive_view(request, slug=None):
    """Combined archive index + category view."""
    categories = ArchiveCategory.objects.all()
    library_books = LibraryBook.objects.all().order_by('-uploaded_at')

    if slug:
        category = get_object_or_404(ArchiveCategory, slug=slug)
        archive_items = ArchiveItem.objects.filter(category=category).order_by('-id')
        featured_record = ArchiveItem.objects.filter(category=category, is_featured=True).first()
        active_category = slug
    else:
        archive_items = ArchiveItem.objects.all().order_by('-id')
        featured_record = ArchiveItem.objects.filter(is_featured=True).first()
        active_category = None

    context = {
        'categories': categories,
        'archive_items': archive_items,
        'featured_record': featured_record,
        'active_category': active_category,
        'library_books': library_books,
    }
    context.update(get_leaderboard_data(request))
    return render(request, 'archive_repository.html', context)


@login_required
def library_view(request):
    """Show all library books. Instructors can upload new books here."""
    books = LibraryBook.objects.all().order_by('-uploaded_at')

    if request.method == 'POST' and request.user.is_authenticated and request.user.role == 'instructor':
        title = request.POST.get('title', '').strip()
        uploaded_file = request.FILES.get('file')
        if title and uploaded_file:
            LibraryBook.objects.create(
                title=title, description=request.POST.get('description', '').strip(),
                file=uploaded_file, thumbnail=request.FILES.get('thumbnail'),
                uploaded_by=request.user,
            )
            trigger_sync_after_action()  # push new book upstream ASAP
            return redirect('library')

    return render(request, 'library.html', {'books': books})


@login_required
def library_download_view(request, book_id):
    """Download a library book file."""
    from django.http import FileResponse
    book = get_object_or_404(LibraryBook, id=book_id)
    return FileResponse(book.file.open('rb'), as_attachment=True, filename=book.file.name)


@login_required
def library_delete_view(request, book_id):
    """Delete a library book (instructor only)."""
    if request.user.role != 'instructor':
        return redirect('home')
    book = get_object_or_404(LibraryBook, id=book_id)
    if request.method == 'POST':
        book.file.delete(save=False)
        if book.thumbnail:
            book.thumbnail.delete(save=False)
        book.delete()
        return redirect('library')
    return redirect('library')



# VIEWS: Quiz System


@login_required
def student_take_quiz_view(request, quiz_id):
    """Student submits answers for a quiz."""
    if request.user.role != 'student':
        return redirect('home')

    quiz = get_object_or_404(Quiz, id=quiz_id)

    existing = StudentQuizSubmission.objects.filter(student=request.user, quiz=quiz).first()
    if existing:
        return redirect('student_quiz_result', quiz_id=quiz_id)

    questions = list(quiz.questions.prefetch_related('choices').all())
    for q in questions:
        q.shuffled_choices = list(q.choices.all())
        random.shuffle(q.shuffled_choices)

    if request.method == 'POST':
        score = 0
        total = len(questions)
        answers = {}
        for question in questions:
            choice_id = request.POST.get(f'question_{question.id}')
            if choice_id:
                selected_choice = get_object_or_404(Choice, id=choice_id, question=question)
                answers[str(question.id)] = int(choice_id)
                if selected_choice.is_correct:
                    score += 1

        StudentQuizSubmission.objects.create(
            student=request.user, quiz=quiz, score=score, total=total, answers=answers,
        )
        request.user.xp = (request.user.xp or 0) + (score * 50)
        request.user.save(update_fields=['xp'])
        trigger_sync_after_action()  # push quiz result upstream ASAP
        return redirect('student_quiz_result', quiz_id=quiz_id)

    return render(request, 'student_take_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def student_quiz_result_view(request, quiz_id):
    """Student views their quiz result."""
    if request.user.role != 'student':
        return redirect('home')

    quiz = get_object_or_404(Quiz, id=quiz_id)
    submission = get_object_or_404(StudentQuizSubmission, student=request.user, quiz=quiz)
    questions = quiz.questions.prefetch_related('choices').all()

    return render(request, 'student_quiz_result.html', {
        'quiz': quiz,
        'submission': submission,
        'results': build_question_results(submission, questions),
    })


@login_required
def instructor_quiz_submissions_view(request, quiz_id):
    """Instructor views all student submissions for a quiz, including answers."""
    if request.user.role != 'instructor':
        return redirect('home')

    quiz = get_object_or_404(Quiz, id=quiz_id)
    if quiz.academic_class and quiz.academic_class.instructor != request.user:
        return redirect('home')

    submissions = StudentQuizSubmission.objects.filter(quiz=quiz).select_related('student').order_by('-score')
    questions = list(quiz.questions.prefetch_related('choices').all())

    submission_data = [
        {'student': sub.student, 'submission': sub, 'question_results': build_question_results(sub, questions)}
        for sub in submissions
    ]

    enrolled_students = quiz.academic_class.students.all() if quiz.academic_class else []
    submitted_ids = {s.student_id for s in submissions}
    pending_students = [s for s in enrolled_students if s.id not in submitted_ids]

    return render(request, 'instructor_quiz_submissions.html', {
        'quiz': quiz, 'submission_data': submission_data, 'pending_students': pending_students,
        'questions': questions, 'total_submissions': submissions.count(),
        'total_enrolled': enrolled_students.count(),
    })


@login_required
def instructor_student_performance_view(request, slug, student_id):
    """Instructor views a specific student's performance across all quizzes in a class."""
    if request.user.role != 'instructor':
        return redirect('home')

    academic_class = get_object_or_404(AcademicClass, slug=slug, instructor=request.user)
    student = get_object_or_404(User, id=student_id, role='student')

    if student not in academic_class.students.all():
        return redirect('instructor_class', slug=slug)

    quizzes = academic_class.quizzes.prefetch_related('questions__choices').all()
    submissions = StudentQuizSubmission.objects.filter(student=student, quiz__in=quizzes).select_related('quiz')
    submission_map = {s.quiz_id: s for s in submissions}

    quiz_results = [
        {
            'quiz': quiz,
            'submission': submission_map.get(quiz.id),
            'has_submitted': submission_map.get(quiz.id) is not None,
            'question_details': build_question_results(submission_map[quiz.id], quiz.questions.all())
            if quiz.id in submission_map else [],
        }
        for quiz in quizzes
    ]

    return render(request, 'instructor_student_performance.html', {
        'class': academic_class, 'student': student, 'quiz_results': quiz_results,
        'total_quizzes': quizzes.count(), 'completed_quizzes': submissions.count(),
        'total_score': sum(s.score for s in submissions),
        'total_possible': sum(s.total for s in submissions),
    })
