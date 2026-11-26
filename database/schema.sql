-- Initial schema for a fresh development Supabase project.
-- Apply as the database owner so the private policy helpers can read their backing tables.
begin;

create schema app_private;
revoke all on schema app_private from public, anon, authenticated, service_role;
grant usage on schema app_private to authenticated, service_role;

create table public.students (
    student_id bigint generated always as identity primary key,
    display_name text not null check (btrim(display_name) <> ''),
    auth_user_id uuid unique references auth.users (id) on delete set null
);

create table public.semesters (
    semester_id bigint generated always as identity primary key,
    semester_code text not null unique check (btrim(semester_code) <> ''),
    semester_name text not null check (btrim(semester_name) <> ''),
    term_order integer not null unique check (term_order > 0),
    starts_on date not null check (isfinite(starts_on)),
    ends_on date not null check (isfinite(ends_on)),
    next_semester_id bigint unique references public.semesters (semester_id),
    forecast_cutoff_at timestamptz check (isfinite(forecast_cutoff_at)),
    check (ends_on >= starts_on),
    check (next_semester_id <> semester_id),
    -- Forecasts reference this pair so publishing them fixes their target term.
    unique (semester_id, next_semester_id)
);

create table public.modules (
    module_id bigint generated always as identity primary key,
    module_code text not null unique check (btrim(module_code) <> ''),
    module_name text not null check (btrim(module_name) <> '')
);

-- Keep the teacher on each term-specific offering to retain historical scope.
create table public.module_offerings (
    offering_id bigint generated always as identity primary key,
    module_id bigint not null references public.modules (module_id),
    semester_id bigint not null references public.semesters (semester_id),
    section_code text not null check (btrim(section_code) <> ''),
    teacher_auth_user_id uuid not null references auth.users (id),
    unique (module_id, semester_id, section_code)
);

-- The trusted academic writer supplies assignments and released results.
create table public.module_enrolments (
    offering_id bigint not null references public.module_offerings (offering_id),
    student_id bigint not null references public.students (student_id),
    attendance_percent numeric check (attendance_percent between 0 and 100),
    completed_at timestamptz check (isfinite(completed_at)),
    actual_score_percent numeric check (actual_score_percent between 0 and 100),
    grade_points numeric check (grade_points between 0 and 4),
    gpa_credits numeric check (gpa_credits > 0 and gpa_credits < 'Infinity'::numeric),
    is_module_at_risk boolean generated always as (actual_score_percent <= 55) stored,
    primary key (offering_id, student_id),
    check (num_nonnulls(completed_at, actual_score_percent, grade_points, gpa_credits) in (0, 4))
);

create table public.semester_records (
    student_id bigint not null references public.students (student_id),
    semester_id bigint not null references public.semesters (semester_id),
    finalized_at timestamptz not null check (isfinite(finalized_at)),
    semester_gpa numeric not null check (semester_gpa between 0 and 4),
    cumulative_gpa numeric not null check (cumulative_gpa between 0 and 4),
    semester_gpa_credits numeric check (
        semester_gpa_credits > 0 and semester_gpa_credits < 'Infinity'::numeric
    ),
    cumulative_gpa_credits numeric check (
        cumulative_gpa_credits > 0 and cumulative_gpa_credits < 'Infinity'::numeric
    ),
    expected_next_semester_credits numeric check (
        expected_next_semester_credits >= 0 and expected_next_semester_credits < 'Infinity'::numeric
    ),
    attendance numeric check (attendance between 0 and 100),
    assignment_score numeric check (assignment_score between 0 and 100),
    quiz_score numeric check (quiz_score between 0 and 100),
    midterm_marks numeric check (midterm_marks between 0 and 100),
    final_marks numeric check (final_marks between 0 and 100),
    study_hours_week numeric check (study_hours_week >= 0 and study_hours_week < 'Infinity'::numeric),
    backlog_subjects integer check (backlog_subjects >= 0),
    workload_level integer check (workload_level between 1 and 10),
    record_revision bigint not null default 1 check (record_revision > 0),
    -- The future finalizer certifies this revision after reconciling module results and credits.
    reconciled_revision bigint check (reconciled_revision between 1 and record_revision),
    record_origin text not null default 'synthetic_demo' check (record_origin = 'synthetic_demo'),
    kaggle_source_ref text check (btrim(kaggle_source_ref) <> ''),
    kaggle_feature_names text[] not null default '{}',
    primary key (student_id, semester_id),
    check (cumulative_gpa_credits >= semester_gpa_credits),
    -- The reference identifies a versioned CSV row. Unlisted inputs and the
    -- recorded GPAs come from the demo, with GPAs calculated from module results.
    check ((kaggle_source_ref is null) = (cardinality(kaggle_feature_names) = 0)),
    check (array_position(kaggle_feature_names, null) is null),
    check (kaggle_feature_names <@ array[
        'attendance', 'assignment_score', 'quiz_score', 'midterm_marks',
        'final_marks', 'study_hours_week', 'backlog_subjects', 'workload_level'
    ])
);

create function app_private.bound_gpa(raw_gpa double precision)
returns double precision
language sql immutable strict
set search_path = ''
as $$
    select greatest(0::double precision, least(4::double precision, raw_gpa));
$$;

create table public.forecasts (
    student_id bigint not null,
    source_semester_id bigint not null,
    target_semester_id bigint not null,
    source_record_revision bigint not null check (source_record_revision > 0),
    model_artifact text not null check (btrim(model_artifact) <> ''),
    published_at timestamptz not null default now() check (isfinite(published_at)),
    first_published_at timestamptz not null check (isfinite(first_published_at)),
    republication_reason text check (btrim(republication_reason) <> ''),
    projection_updated_at timestamptz not null check (isfinite(projection_updated_at)),
    raw_predicted_gpa double precision check (
        raw_predicted_gpa > '-Infinity'::double precision
        and raw_predicted_gpa < 'Infinity'::double precision
    ),
    displayed_predicted_gpa double precision generated always as (
        app_private.bound_gpa(raw_predicted_gpa)
    ) stored,
    is_predicted_gpa_at_risk boolean generated always as (
        raw_predicted_gpa <= 2.2::double precision
    ) stored,
    projected_cgpa numeric check (projected_cgpa between 0 and 4),
    is_projected_cgpa_at_risk boolean generated always as (projected_cgpa <= 2.2) stored,
    primary key (student_id, source_semester_id),
    foreign key (student_id, source_semester_id)
        references public.semester_records (student_id, semester_id),
    foreign key (source_semester_id, target_semester_id)
        references public.semesters (semester_id, next_semester_id),
    check (first_published_at <= published_at),
    check (raw_predicted_gpa is not null or projected_cgpa is null)
);

create index module_offerings_teacher_idx on public.module_offerings (teacher_auth_user_id, semester_id);
create index module_offerings_term_idx on public.module_offerings (semester_id);
create index module_enrolments_student_idx on public.module_enrolments (student_id, offering_id);
create index semester_records_term_idx on public.semester_records (semester_id);
create index forecasts_source_term_idx on public.forecasts (source_semester_id, target_semester_id);

-- A student's published estimates remain available across semesters while valid.
create view app_private.valid_published_forecasts with (security_invoker = true) as
select forecast.student_id, forecast.source_semester_id
from public.forecasts as forecast
join public.semesters as source on source.semester_id = forecast.source_semester_id
join public.semesters as target on target.semester_id = forecast.target_semester_id
join public.semester_records as record
  on record.student_id = forecast.student_id and record.semester_id = forecast.source_semester_id
where target.term_order > source.term_order
  and record.finalized_at <= source.forecast_cutoff_at
  and forecast.published_at between source.forecast_cutoff_at and statement_timestamp()
  and forecast.source_record_revision = record.record_revision
  and record.reconciled_revision = record.record_revision;

revoke all on app_private.valid_published_forecasts from public, anon, authenticated, service_role;

-- A later correction to any scoring input makes published forecasts stale.
create function app_private.revise_semester_record()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if row(
        new.finalized_at, new.semester_gpa, new.cumulative_gpa, new.attendance,
        new.assignment_score, new.quiz_score, new.midterm_marks, new.final_marks,
        new.study_hours_week, new.backlog_subjects, new.workload_level
    ) is distinct from row(
        old.finalized_at, old.semester_gpa, old.cumulative_gpa, old.attendance,
        old.assignment_score, old.quiz_score, old.midterm_marks, old.final_marks,
        old.study_hours_week, old.backlog_subjects, old.workload_level
    ) then
        new.record_revision := greatest(new.record_revision, old.record_revision + 1);
    else
        new.record_revision := greatest(new.record_revision, old.record_revision);
    end if;
    return new;
end;
$$;

create trigger revise_semester_record
    before update on public.semester_records
    for each row execute function app_private.revise_semester_record();

create function app_private.preserve_enrolled_offering()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if row(new.module_id, new.semester_id) is distinct from row(old.module_id, old.semester_id)
       and exists (select 1 from public.module_enrolments as enrolment
                   where enrolment.offering_id = old.offering_id) then
        raise exception 'An offering with enrolments cannot change module or semester'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

create trigger preserve_enrolled_offering
    before update of module_id, semester_id on public.module_offerings
    for each row execute function app_private.preserve_enrolled_offering();

-- Completed results can affect the CGPA of every later term. Pending roster
-- entries and their attendance updates do not change completed academic history.
-- The trusted academic writer must recompute those summaries in the same transaction.
create function app_private.invalidate_forecasts_after_module_result_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if tg_op = 'UPDATE' and old is not distinct from new then
        return null;
    end if;

    if tg_op <> 'DELETE' and new.completed_at > statement_timestamp() then
        raise exception 'A completed module result cannot be dated in the future'
            using errcode = '23514';
    end if;

    update public.semester_records as record
    set record_revision = record.record_revision + 1
    from public.semesters as record_term
    where record_term.semester_id = record.semester_id
      and exists (
          select 1
          from (values
              (case when tg_op <> 'INSERT' then old.student_id end,
               case when tg_op <> 'INSERT' and old.completed_at is not null then old.offering_id end),
              (case when tg_op <> 'DELETE' then new.student_id end,
               case when tg_op <> 'DELETE' and new.completed_at is not null then new.offering_id end)
          ) as changed (student_id, offering_id)
          join public.module_offerings as offering on offering.offering_id = changed.offering_id
          join public.semesters as changed_term on changed_term.semester_id = offering.semester_id
          where changed.student_id = record.student_id
            and changed_term.term_order <= record_term.term_order
      );
    return null;
end;
$$;

create trigger invalidate_forecasts_after_module_result_change
    after insert or update or delete on public.module_enrolments
    for each row execute function app_private.invalidate_forecasts_after_module_result_change();

-- The publisher supplies the raw score and the revision it actually scored.
-- PostgreSQL derives projected CGPA from that source record's credits.
create function app_private.prepare_forecast()
returns trigger
language plpgsql security definer
set search_path = ''
as $$
declare
    source_record public.semester_records%rowtype;
    source_cutoff timestamptz;
begin
    select record.* into strict source_record
    from public.semester_records as record
    where record.student_id = new.student_id and record.semester_id = new.source_semester_id
    for share;

    if new.source_record_revision <> source_record.record_revision then
        raise exception 'Forecast must use the current source record revision'
            using errcode = '23514';
    end if;

    if source_record.reconciled_revision is distinct from source_record.record_revision then
        raise exception 'Forecast requires a reconciled semester record'
            using errcode = '23514';
    end if;

    select source.forecast_cutoff_at into source_cutoff
    from public.semesters as source
    join public.semesters as target on target.semester_id = source.next_semester_id
    where source.semester_id = new.source_semester_id
      and target.semester_id = new.target_semester_id
      and target.term_order > source.term_order;

    if source_cutoff is null or source_record.finalized_at > source_cutoff
       or new.published_at < source_cutoff or new.published_at > statement_timestamp() then
        raise exception 'Forecast publication must match an approved completed semester cutoff'
            using errcode = '23514';
    end if;

    new.projected_cgpa := null;
    new.republication_reason := nullif(btrim(new.republication_reason), '');

    if new.raw_predicted_gpa is not null then
        if num_nulls(
            source_record.attendance, source_record.assignment_score, source_record.quiz_score,
            source_record.midterm_marks, source_record.final_marks, source_record.study_hours_week,
            source_record.backlog_subjects, source_record.workload_level
        ) > 0 then
            raise exception 'A scored forecast requires all source model inputs'
                using errcode = '23514';
        end if;
        if source_record.cumulative_gpa_credits is not null
           and source_record.expected_next_semester_credits > 0 then
            new.projected_cgpa := (
                source_record.cumulative_gpa * source_record.cumulative_gpa_credits
                + app_private.bound_gpa(new.raw_predicted_gpa)::numeric
                  * source_record.expected_next_semester_credits
            ) / (source_record.cumulative_gpa_credits + source_record.expected_next_semester_credits);
        end if;
    end if;

    if tg_op = 'INSERT' then
        new.first_published_at := new.published_at;
        new.projection_updated_at := new.published_at;
    else
        if row(new.student_id, new.source_semester_id, new.target_semester_id)
           is distinct from row(old.student_id, old.source_semester_id, old.target_semester_id) then
            raise exception 'Published forecast identity and semesters cannot change'
                using errcode = '23514';
        end if;

        if new.published_at > old.published_at then
            if new.republication_reason is null
               or new.republication_reason is not distinct from old.republication_reason then
                raise exception 'Republishing a forecast requires a new correction reason'
                    using errcode = '23514';
            end if;
        elsif new.published_at < old.published_at or row(
            new.source_record_revision, new.raw_predicted_gpa, new.model_artifact,
            new.republication_reason, new.projected_cgpa
        ) is distinct from row(
            old.source_record_revision, old.raw_predicted_gpa, old.model_artifact,
            old.republication_reason, old.projected_cgpa
        ) then
            raise exception 'A forecast correction requires a newer publication time and a reason'
                using errcode = '23514';
        end if;

        new.first_published_at := old.first_published_at;
        new.projection_updated_at := old.projection_updated_at;
        if new.projected_cgpa is distinct from old.projected_cgpa then
            new.projection_updated_at := statement_timestamp();
        end if;
    end if;
    return new;
end;
$$;

create trigger prepare_forecast
    before insert or update on public.forecasts
    for each row execute function app_private.prepare_forecast();

-- Read across protected tables without recursive policies. These functions
-- derive the actor from Supabase Auth and live in a non-exposed schema.
create function app_private.current_app_role()
returns text
language sql stable security definer
set search_path = ''
as $$
    -- Use live, administrator-managed metadata so role changes take effect before token refresh.
    select account.raw_app_meta_data ->> 'app_role'
    from auth.users as account
    where account.id = (select auth.uid())
      and account.raw_app_meta_data ->> 'app_role' in ('student', 'module_teacher');
$$;

create function app_private.current_student_id()
returns bigint
language sql stable security definer
set search_path = ''
as $$
    select student.student_id
    from public.students as student
    where student.auth_user_id = (select auth.uid())
      and (select app_private.current_app_role()) = 'student'
      and not exists (
          select 1 from public.module_offerings as offering
          where offering.teacher_auth_user_id = (select auth.uid())
      );
$$;

create function app_private.teacher_has_enrolled_student(requested_student_id bigint)
returns boolean
language sql stable security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.module_enrolments as enrolment
        join public.module_offerings as offering on offering.offering_id = enrolment.offering_id
        where enrolment.student_id = requested_student_id
          and (select app_private.current_app_role()) = 'module_teacher'
          and offering.teacher_auth_user_id = (select auth.uid())
    );
$$;

-- Read the caller's own enrolment without recursively applying offering policies.
create function app_private.student_is_enrolled_in_offering(requested_offering_id bigint)
returns boolean
language sql stable security definer
set search_path = ''
as $$
    select exists (
        select 1 from public.module_enrolments as enrolment
        where enrolment.offering_id = requested_offering_id
          and enrolment.student_id = (select app_private.current_student_id())
    );
$$;

create function app_private.can_read_student_forecast(
    requested_student_id bigint, requested_source_semester_id bigint
)
returns boolean
language sql stable security definer
set search_path = ''
as $$
    select exists (
        select 1
        from app_private.valid_published_forecasts as forecast
        where forecast.student_id = (select app_private.current_student_id())
          and forecast.student_id = requested_student_id
          and forecast.source_semester_id = requested_source_semester_id
    );
$$;

revoke all on all functions in schema app_private from public, anon, authenticated, service_role;
grant execute on function app_private.current_app_role(), app_private.current_student_id(),
    app_private.teacher_has_enrolled_student(bigint),
    app_private.student_is_enrolled_in_offering(bigint),
    app_private.can_read_student_forecast(bigint, bigint) to authenticated;
grant execute on function app_private.bound_gpa(double precision) to service_role;

alter table public.students enable row level security;
alter table public.semesters enable row level security;
alter table public.modules enable row level security;
alter table public.module_offerings enable row level security;
alter table public.module_enrolments enable row level security;
alter table public.semester_records enable row level security;
alter table public.forecasts enable row level security;

-- Supabase can grant table-wide access by default. Revoke it before granting
-- display columns so clients cannot select raw scores or private model inputs.
revoke all on public.students, public.semesters, public.modules, public.module_offerings,
    public.module_enrolments, public.semester_records, public.forecasts
    from public, anon, authenticated, service_role;

grant select (student_id, display_name) on public.students to authenticated;
grant select (semester_id, semester_code, semester_name, term_order, starts_on, ends_on,
    next_semester_id) on public.semesters to authenticated;
grant select (module_id, module_code, module_name) on public.modules to authenticated;
grant select (offering_id, module_id, semester_id, section_code)
    on public.module_offerings to authenticated;
grant select (offering_id, student_id, attendance_percent, completed_at,
    actual_score_percent, grade_points, is_module_at_risk)
    on public.module_enrolments to authenticated;
grant select (student_id, semester_id, finalized_at, semester_gpa, cumulative_gpa, record_origin)
    on public.semester_records to authenticated;
grant select (student_id, source_semester_id, target_semester_id, first_published_at,
    published_at, projection_updated_at,
    displayed_predicted_gpa, projected_cgpa, is_predicted_gpa_at_risk, is_projected_cgpa_at_risk)
    on public.forecasts to authenticated;

-- Hold academic writes until a trusted transactional finalizer can reconcile and certify them.
grant select on public.semester_records, public.module_enrolments to service_role;
grant select, insert, update on public.students, public.semesters, public.modules,
    public.module_offerings, public.forecasts to service_role;
revoke all on sequence public.students_student_id_seq, public.semesters_semester_id_seq,
    public.modules_module_id_seq, public.module_offerings_offering_id_seq
    from public, anon, authenticated, service_role;
grant usage on sequence public.students_student_id_seq, public.semesters_semester_id_seq,
    public.modules_module_id_seq, public.module_offerings_offering_id_seq to service_role;

create policy read_authorized_students on public.students
    for select to authenticated
    using (
        student_id = (select app_private.current_student_id())
        or app_private.teacher_has_enrolled_student(student_id)
    );

create policy read_semester_calendar on public.semesters
    for select to authenticated using (true);

create policy read_module_catalog on public.modules
    for select to authenticated using (true);

create policy read_authorized_module_offerings on public.module_offerings
    for select to authenticated
    using (
        ((select app_private.current_app_role()) = 'module_teacher'
            and teacher_auth_user_id = (select auth.uid()))
        or app_private.student_is_enrolled_in_offering(offering_id)
    );

-- A student's permission to see an offering does not grant access to its roster.
create policy read_authorized_module_enrolments on public.module_enrolments
    for select to authenticated
    using (
        student_id = (select app_private.current_student_id())
        or (
            (select app_private.current_app_role()) = 'module_teacher'
            and exists (
                select 1 from public.module_offerings as offering
                where offering.offering_id = module_enrolments.offering_id
            )
        )
    );

create policy read_own_reconciled_semester_records on public.semester_records
    for select to authenticated
    using (
        student_id = (select app_private.current_student_id())
        and finalized_at <= statement_timestamp()
        and reconciled_revision = record_revision
    );

create policy read_own_published_forecasts on public.forecasts
    for select to authenticated
    using (app_private.can_read_student_forecast(student_id, source_semester_id));

commit;
