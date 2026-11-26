-- Template for database.seed. Execute the generated transaction as the database owner.
-- Demo rows use reserved negative IDs. The transaction never deletes academic rows.
begin;
set local search_path = pg_catalog, pg_temp;
set local timezone = 'UTC';
set local standard_conforming_strings = on;

do $$
begin
    if current_user <> (select tableowner from pg_tables where schemaname='public' and tablename='students') then
        raise insufficient_privilege using message = 'Run the demo seed as the database owner';
    end if;
end;
$$;

-- Serialize demo runs and exclude other writers during reconciliation. Reads can continue.
lock table public.students, public.semesters, public.modules, public.module_offerings,
    public.module_enrolments, public.semester_records in share row exclusive mode;

-- DEMO_INPUT

create temporary table demo_students on commit drop as
select x.* from pg_temp.demo_input,
    jsonb_to_recordset(payload->'students') as x(student_id bigint, display_name text);
alter table pg_temp.demo_students add primary key (student_id);

create temporary table demo_terms on commit drop as
select x.* from pg_temp.demo_input,
    jsonb_to_recordset(payload->'terms') as x(semester_id bigint, semester_code text, semester_name text,
        term_order integer, starts_on date, ends_on date, next_semester_id bigint,
        finalized_at timestamptz, forecast_cutoff_at timestamptz);
alter table pg_temp.demo_terms add primary key (semester_id);

create temporary table demo_modules on commit drop as
select x.*, u.id as teacher_auth_user_id from pg_temp.demo_input
cross join lateral jsonb_to_recordset(payload->'modules') as x(module_id bigint, module_code text,
    module_name text, semester_id bigint, offering_id bigint, teacher_email text, gpa_credits numeric)
left join auth.users u on u.email=x.teacher_email and u.raw_app_meta_data->>'app_role'='module_teacher';
alter table pg_temp.demo_modules add primary key (offering_id);

create temporary table demo_results on commit drop as
select x.offering_id, x.student_id, x.attendance_percent, x.actual_score_percent,
    case when x.actual_score_percent is not null then t.finalized_at - interval '1 day' end as completed_at,
    case when x.actual_score_percent is not null then m.gpa_credits end as gpa_credits,
    (select max(g.points) from jsonb_to_recordset(payload->'grade_scale') as g(minimum numeric, points numeric)
        where x.actual_score_percent >= g.minimum) as grade_points
from pg_temp.demo_input
cross join lateral jsonb_to_recordset(payload->'results') as x(offering_id bigint, student_id bigint,
    attendance_percent numeric, actual_score_percent numeric)
left join pg_temp.demo_modules m using (offering_id)
left join pg_temp.demo_terms t using (semester_id);
alter table pg_temp.demo_results add primary key (offering_id, student_id);

create temporary table demo_snapshots on commit drop as
select x.* from pg_temp.demo_input,
    jsonb_to_recordset(payload->'summaries') as x(student_id bigint, semester_id bigint, semester_gpa numeric,
        cumulative_gpa numeric, semester_gpa_credits numeric, cumulative_gpa_credits numeric,
        expected_next_semester_credits numeric, attendance numeric, backlog_subjects integer,
        assignment_score numeric, quiz_score numeric, midterm_marks numeric, final_marks numeric,
        study_hours_week numeric, workload_level integer, kaggle_source_ref text, kaggle_feature_names text[]);
alter table pg_temp.demo_snapshots add primary key (student_id, semester_id);

do $$
begin
    if exists (select 1 from pg_temp.demo_modules where teacher_auth_user_id is null) then
        raise exception 'The three demo teacher Auth accounts must exist with app_role=module_teacher';
    end if;
    if exists (select 1 from pg_temp.demo_students where student_id >= 0 or display_name not like 'Demo Student %')
       or exists (select 1 from pg_temp.demo_terms where semester_id >= 0 or semester_code not like 'DEMO-%')
       or exists (select 1 from pg_temp.demo_modules where module_id >= 0 or offering_id >= 0 or module_code not like 'DEMO-%'
                  or gpa_credits is null or gpa_credits <= 0 or gpa_credits >= 'Infinity'::numeric) then
        raise exception 'Expected reserved demo identities and positive module credits';
    end if;
    if exists (
        select 1 from pg_temp.demo_terms t
        left join pg_temp.demo_terms n on n.semester_id = t.next_semester_id
        where (t.finalized_at is null) <> (t.forecast_cutoff_at is null)
           or (t.finalized_at is not null and (
                n.term_order is distinct from t.term_order + 1 or t.finalized_at <= t.ends_on
                or t.finalized_at > statement_timestamp() or t.finalized_at > t.forecast_cutoff_at
           ))
    ) or exists (
        select 1 from pg_temp.demo_modules m cross join pg_temp.demo_students s
        left join pg_temp.demo_terms t on t.semester_id=m.semester_id
        left join pg_temp.demo_results r on r.student_id=s.student_id and r.offering_id=m.offering_id
        where t.semester_id is null or r.student_id is null
           or (t.finalized_at is not null and (r.actual_score_percent is null or r.attendance_percent is null))
           or (t.finalized_at is null and (r.actual_score_percent is not null or r.attendance_percent is not null))
    ) or exists (
        select 1 from pg_temp.demo_results r
        where not exists (select 1 from pg_temp.demo_students s where s.student_id=r.student_id)
           or not exists (select 1 from pg_temp.demo_modules m where m.offering_id=r.offering_id)
    ) then
        raise exception 'Demo roster, result completeness or calendar does not reconcile';
    end if;
    if exists (
        select 1 from pg_temp.demo_snapshots where num_nulls(
            assignment_score, quiz_score, midterm_marks, final_marks, study_hours_week,
            workload_level, kaggle_source_ref, kaggle_feature_names
        ) > 0 or study_hours_week not between 0 and 168 or backlog_subjects not between 0 and 20
          or kaggle_feature_names is distinct from array[
              'attendance','assignment_score','quiz_score','midterm_marks','final_marks','study_hours_week','workload_level'
          ]::text[]
    ) then
        raise exception 'A completed demo snapshot requires the seven matched Kaggle inputs and valid behaviour features';
    end if;
end;
$$;

insert into public.students (student_id, display_name) overriding system value
select student_id, display_name from pg_temp.demo_students on conflict (student_id) do nothing;

insert into public.semesters (semester_id, semester_code, semester_name, term_order, starts_on, ends_on,
    next_semester_id, forecast_cutoff_at) overriding system value
select semester_id, semester_code, semester_name, term_order, starts_on, ends_on,
    next_semester_id, forecast_cutoff_at from pg_temp.demo_terms on conflict (semester_id) do nothing;

insert into public.modules (module_id, module_code, module_name) overriding system value
select module_id, module_code, module_name from pg_temp.demo_modules on conflict (module_id) do nothing;

insert into public.module_offerings (offering_id, module_id, semester_id, section_code, teacher_auth_user_id)
overriding system value
select offering_id, module_id, semester_id, 'DEMO', teacher_auth_user_id
from pg_temp.demo_modules on conflict (offering_id) do nothing;

do $$
begin
    -- Preserve existing Auth links and refuse to take over IDs or assignments.
    if exists (
        select 1 from pg_temp.demo_students d join public.students s using (student_id)
        where s.display_name is distinct from d.display_name
    ) or exists (
        select 1 from pg_temp.demo_terms d join public.semesters t using (semester_id)
        where row(t.semester_code,t.semester_name,t.term_order,t.starts_on,t.ends_on,t.next_semester_id,t.forecast_cutoff_at)
          is distinct from row(d.semester_code,d.semester_name,d.term_order,d.starts_on,d.ends_on,d.next_semester_id,d.forecast_cutoff_at)
    ) or exists (
        select 1 from pg_temp.demo_modules d
        join public.modules m using (module_id) join public.module_offerings o using (offering_id)
        where row(m.module_code,m.module_name,o.module_id,o.semester_id,o.teacher_auth_user_id,o.section_code)
          is distinct from row(d.module_code,d.module_name,d.module_id,d.semester_id,d.teacher_auth_user_id,'DEMO'::text)
    ) then
        raise exception 'Existing identity, module assignment or calendar differs from the demo definition';
    end if;
    if exists (
        select 1 from public.module_enrolments e
        where (e.student_id in (select student_id from pg_temp.demo_students)
            or e.offering_id in (select offering_id from pg_temp.demo_modules))
          and not exists (select 1 from pg_temp.demo_results d
                          where (d.offering_id,d.student_id)=(e.offering_id,e.student_id))
    ) or exists (
        select 1 from public.semester_records r
        where r.student_id in (select student_id from pg_temp.demo_students)
          and not exists (select 1 from pg_temp.demo_snapshots d
                          where (d.student_id,d.semester_id)=(r.student_id,r.semester_id))
    ) then
        raise exception 'Unrecognised academic records overlap the demo cohort';
    end if;
    if not (select allow_corrections from pg_temp.demo_input) and exists (
        select 1 from pg_temp.demo_results d join public.module_enrolments e using (offering_id,student_id)
        where row(e.attendance_percent,e.completed_at,e.actual_score_percent,e.grade_points,e.gpa_credits)
          is distinct from row(d.attendance_percent,d.completed_at,d.actual_score_percent,d.grade_points,d.gpa_credits)
    ) then
        raise exception 'A demo module result differs. Review the change before enabling corrections';
    end if;
end;
$$;

insert into public.module_enrolments as e (offering_id, student_id, attendance_percent, completed_at,
    actual_score_percent, grade_points, gpa_credits)
select offering_id, student_id, attendance_percent, completed_at, actual_score_percent, grade_points, gpa_credits
from pg_temp.demo_results
on conflict (offering_id,student_id) do update set attendance_percent=excluded.attendance_percent,
    completed_at=excluded.completed_at, actual_score_percent=excluded.actual_score_percent,
    grade_points=excluded.grade_points, gpa_credits=excluded.gpa_credits
where row(e.attendance_percent,e.completed_at,e.actual_score_percent,e.grade_points,e.gpa_credits)
  is distinct from row(excluded.attendance_percent,excluded.completed_at,excluded.actual_score_percent,
                       excluded.grade_points,excluded.gpa_credits);

-- Derive summaries from the persisted module results and unrounded quality points.
create temporary table demo_calculated on commit drop as
with term_totals as (
    select e.student_id, t.semester_id, t.term_order, t.finalized_at, t.next_semester_id,
        sum(e.gpa_credits) as credits,
        sum(e.gpa_credits * e.grade_points) as quality_points,
        sum(e.gpa_credits * e.attendance_percent) / sum(e.gpa_credits) as weighted_attendance,
        count(*) filter (where e.grade_points=0) as failed_modules
    from public.module_enrolments e
    join pg_temp.demo_results d using (offering_id,student_id)
    join public.module_offerings o using (offering_id)
    join pg_temp.demo_terms t using (semester_id)
    where e.completed_at is not null
    group by e.student_id, t.semester_id, t.term_order, t.finalized_at, t.next_semester_id
), cumulative as (
    select *, sum(credits) over history as cumulative_credits,
        sum(quality_points) over history as cumulative_points,
        sum(failed_modules) over history as total_failed_modules
    from term_totals window history as (partition by student_id order by term_order)
)
select student_id, semester_id, finalized_at, round(quality_points / credits,12) as semester_gpa,
    round(cumulative_points / cumulative_credits,12) as cumulative_gpa, credits as semester_gpa_credits,
    cumulative_credits as cumulative_gpa_credits, round(weighted_attendance, 2) as attendance,
    weighted_attendance, total_failed_modules::integer as backlog_subjects,
    (select sum(m.gpa_credits) from pg_temp.demo_modules m where m.semester_id=c.next_semester_id)
        as expected_next_semester_credits
from cumulative c;

do $$
begin
    if exists (
        select 1 from pg_temp.demo_calculated c full join pg_temp.demo_snapshots s using (student_id,semester_id)
        where c.student_id is null or s.student_id is null
           or abs(c.weighted_attendance - s.attendance) > 0.00005
           or row(c.semester_gpa,c.cumulative_gpa,c.semester_gpa_credits,c.cumulative_gpa_credits,
                  c.attendance,c.backlog_subjects,c.expected_next_semester_credits)
          is distinct from row(s.semester_gpa,s.cumulative_gpa,s.semester_gpa_credits,s.cumulative_gpa_credits,
                               s.attendance,s.backlog_subjects,s.expected_next_semester_credits)
    ) then
        raise exception 'Calculated GPA, CGPA, attendance, credits or backlog differ from the supplied snapshots';
    end if;
end;
$$;

create temporary table demo_written on commit drop as
with written as (
    insert into public.semester_records as r (student_id, semester_id, finalized_at, semester_gpa, cumulative_gpa,
        semester_gpa_credits, cumulative_gpa_credits, expected_next_semester_credits, attendance,
        assignment_score, quiz_score, midterm_marks, final_marks, study_hours_week, backlog_subjects,
        workload_level, kaggle_source_ref, kaggle_feature_names)
    select c.student_id, c.semester_id, c.finalized_at, c.semester_gpa, c.cumulative_gpa,
        c.semester_gpa_credits, c.cumulative_gpa_credits, c.expected_next_semester_credits, c.attendance,
        s.assignment_score, s.quiz_score, s.midterm_marks, s.final_marks, s.study_hours_week,
        c.backlog_subjects, s.workload_level, s.kaggle_source_ref, s.kaggle_feature_names
    from pg_temp.demo_calculated c join pg_temp.demo_snapshots s using (student_id,semester_id)
    on conflict (student_id,semester_id) do update set
        (finalized_at,semester_gpa,cumulative_gpa,semester_gpa_credits,cumulative_gpa_credits,
         expected_next_semester_credits,attendance,assignment_score,quiz_score,midterm_marks,final_marks,
         study_hours_week,backlog_subjects,workload_level,kaggle_source_ref,kaggle_feature_names,record_revision) =
        (excluded.finalized_at,excluded.semester_gpa,excluded.cumulative_gpa,excluded.semester_gpa_credits,
         excluded.cumulative_gpa_credits,excluded.expected_next_semester_credits,excluded.attendance,
         excluded.assignment_score,excluded.quiz_score,excluded.midterm_marks,excluded.final_marks,
         excluded.study_hours_week,excluded.backlog_subjects,excluded.workload_level,excluded.kaggle_source_ref,
         excluded.kaggle_feature_names,r.record_revision + 1)
    where row(r.finalized_at,r.semester_gpa,r.cumulative_gpa,r.semester_gpa_credits,r.cumulative_gpa_credits,
              r.expected_next_semester_credits,r.attendance,r.assignment_score,r.quiz_score,r.midterm_marks,
              r.final_marks,r.study_hours_week,r.backlog_subjects,r.workload_level,r.kaggle_source_ref,r.kaggle_feature_names)
      is distinct from row(excluded.finalized_at,excluded.semester_gpa,excluded.cumulative_gpa,excluded.semester_gpa_credits,
          excluded.cumulative_gpa_credits,excluded.expected_next_semester_credits,excluded.attendance,
          excluded.assignment_score,excluded.quiz_score,excluded.midterm_marks,excluded.final_marks,
          excluded.study_hours_week,excluded.backlog_subjects,excluded.workload_level,excluded.kaggle_source_ref,excluded.kaggle_feature_names)
    returning record_revision
)
select count(*) filter (where record_revision > 1) as revised from written;

do $$
begin
    if not (select allow_corrections from pg_temp.demo_input) and (select revised from pg_temp.demo_written) > 0 then
        raise exception 'A demo semester snapshot differs. Review the change before enabling corrections';
    end if;
end;
$$;

-- Certify the current revision only after module results and all summaries agree.
update public.semester_records r set reconciled_revision=r.record_revision
from pg_temp.demo_calculated c
where (r.student_id,r.semester_id)=(c.student_id,c.semester_id)
  and r.reconciled_revision is distinct from r.record_revision;

commit;
