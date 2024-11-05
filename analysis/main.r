library(tidyverse)
# remotes::install_github("keller-mark/pizzarr")
source('r/zarr.r') # zarr-reading helpers


zarr_files = fs::dir_ls('../data', glob='*.zarr.zip', recurse=TRUE)

(
	zarr_files
	# %>% .[str_detect(.,'mike')]
	%>% .[str_detect(.,'test')]
	%>% pluck(1)
	%>% process_zarr_file()
) ->
	tbls
names(tbls)
tbls_bak = tbls
# tbls = tbls_bak

(
	tbls$system_stats
	%>% mutate(
		across(
			c('time')
			, ~ .x - tbls$exp$trial_start_time[1]
		)
	)
) ->
	tbls$system_stats

(
	tbls$system_stats
	%>% pivot_longer(c(mem,cpu))
	%>% ggplot()
	+ facet_grid(
		name~.
		, scales='free_y'
	)
	+ geom_line(aes(x=time,y=value))
	# + scale_y_continuous(limits=c(0,100))
)


(
	tbls$eye
	%>% mutate(
		across(
			c('time1','time2')
			, ~ .x - tbls$exp$trial_start_time[1]
		)
	)
) ->
	tbls$eye

(
	tbls$triggers
	%>% mutate(
		across(
			c('time')
			, ~ .x - tbls$exp$trial_start_time[1]
		)
	)
) ->
	tbls$triggers


(
	tbls$exp
	%>% mutate(
		across(
			starts_with('target_on_time')
			, ~ .x - trial_start_time[1]
		)
		, trial_start_time = trial_start_time - trial_start_time[1]
	)
) ->
	tbls$exp



(
	tbls$eye
	%>% mutate(
		dt1 = time2 - time1
		, dt2 = time1 - lag(time2)
		, dt3 = time2 - lag(time2)
	)
	%>% select(
		starts_with('dt')
		# , starts_with('time')
	)
	%>% pivot_longer(everything())
	# %>% filter(value<.1)
	%>% filter(name!='dt1')
	%>% mutate(value=1/value)
	%>% drop_na()
	%>% ggplot()
	+ facet_grid(name~.,scales='free_y')
	+ geom_histogram(aes(x=value),bins=100)
	+ labs(x='Hz')
)


(
	tbls$eye
	%>% mutate(
		# time = (time1+time2)/2
		time = time2
		, hz = 1/(time2 - lag(time2))
	)
	%>% filter(!is.na(hz))
	%>% left_join(
		tbls$exp
		, join_by(closest(time >= trial_start_time))
	)
	%>% mutate(
		trial_time = time - trial_start_time
	)
) ->
	tmp

(
	tmp
	%>% ggplot()
	+ geom_histogram(aes(x=hz),bins=100)
)

(
	tmp
	%>% mutate(
		hz_grp = case_when(
			hz<15 ~ '<15'
			, (hz>=15)&(hz<16) ~ '>=15, <16'
			, (hz>=19)&(hz<21) ~ '>=19, <21'
			, hz>=21 ~ '>=21'
		)
	)
	%>% ggplot()
	+ facet_grid(hz_grp~.,scale='free_y')
	+ geom_histogram(aes(x=trial_time),bins=100)
)

(
	tmp
	%>% filter(trial_time<3)
	%>% ggplot()
	# + facet_grid(name~.,scales='free_y')
	+ geom_line(
		aes(
			x = trial_time
			, y = log(hz)
			, group = trial_num
		)
		, alpha = .1
	)
	+ geom_smooth(
		aes(
			x = trial_time
			, y = log(hz)
		)
		, fill = 'red'
		, method = 'gam'
		, formula = y ~ s(x, bs = "ts",k=10)
	)
	+ labs(y='Hz')
)

(
	tbls$eye
	%>% mutate(
		time = (time1+time2)/2
		, radius = (radius1+radius2)/2
	)
	%>% left_join(
		tbls$exp
		, join_by(closest(time >= trial_start_time))
	)
	%>% select(trial_num,everything())
	%>% mutate(
		.by = trial_num
		, trial_time = time - trial_start_time[1]
		# , radius = radius-radius[1]
	)
	%>% drop_na()

) ->
	tbls$eye

(
	tbls$eye
	%>% filter(trial_num<max(trial_num))
	# %>% filter(
	# 	time>=0
	# 	, time<=80
	# )
	%>% ggplot()
	+ geom_line(
		aes(
			x = time
			, y = radius
		)
		, alpha = .5
	)
	+ geom_vline(
		data = (. %>% select(trial_num,trial_start_time) %>% distinct() )
		, aes(
			xintercept = trial_start_time
		)
		, alpha = .5
	)
)

(
	tbls$eye
	%>% mutate(
		.by = trial_num
		, radius = radius-radius[which.min(abs(trial_time-1))]
	)
	%>% filter(trial_time<=2)
	%>% filter(trial_num>1)
	%>% ggplot()
	# + geom_histogram(aes(x=time),bins=100)
	+ geom_line(
		aes(
			x = trial_time
			, y = radius
			, group = trial_num
		)
		, alpha = .1
	)
	+ geom_smooth(
		aes(
			x = trial_time
			, y = radius
		)
		, fill = 'red'
		, method = 'gam'
		, formula = y ~ s(x, bs = "ts",k=10)
	)
)


(
	tbls$trigger
	%>% left_join(
		tbls$exp
		, join_by(closest(time >= trial_start_time))
	)
	%>% select(trial_num,trial_start_time,target_on_time0,time,everything())
	%>% filter(!is.na(trial_num))
	%>% mutate(
		.by = c(trial_num,trigger)
		, trial_time = time - trial_start_time
		# , radius = radius-radius[1]
	)
	%>% select(trial_num,trial_start_time,target_on_time0,time,trial_time,everything())

) ->
	tbls$trigger


(
	tbls$trigger
	# %>% filter(time<10)
	%>% filter(trial_num==4)
	%>% ggplot(
		aes(
			x = time
			, y = value
			, colour = trigger
			, group = interaction(trigger,trial_num)
		)
	)
	+ facet_grid(trigger~.)
	+ geom_line()
	+ geom_point()
)

(
	tbls$trigger
	%>% mutate(
		.by = trigger
		, dt = c(NA,diff(time))
		, dv = c(NA,diff(value))
	)
	%>% filter(!is.na(dt))
	%>% filter(!is.na(dv))
	%>% mutate(
		dt_grp = case_when(
			dt<.02 ~ 'fast'
			, dt<.2 ~ 'medium'
			, TRUE ~ 'slow'
		)
		, dv_grp = case_when(
			dv>0 ~ 'increasing'
			, dv<0 ~ 'decreasing'
			, TRUE ~ 'other'
		)
	)
	# %>% filter(dt<1)
	%>% filter(dt<.05)
	%>% ggplot()
	+ facet_grid(dv_grp~.)
	+ geom_histogram(aes(x=dt),bins=100))
	# %>% filter(trial_num==5)
	# %>% filter(trigger=='right')
	%>% ggplot(
		aes(
			x = trial_time
			, y = value
			, colour = trigger
			, group = trigger
		)
	)
	# + facet_grid(trigger~.)
	+ facet_wrap(~trial_num)
	+ geom_line(alpha = .5)
	# + geom_point(
	# 	aes(
	# 		colour = dt_grp
	# 		, group = interaction(trial_num,dt_grp)
	# 	)
	# 	, alpha = .5
	# )
)

(
	tbls$trigger
	%>% ggplot(
		aes(
			x = trial_time
			, y = value
			, colour = trigger
			, group = trigger
		)
		,
	)
	+ facet_wrap(~trial_num)
	+ geom_line()
	+ geom_point()
)


(
	tbls$trigger
	%>% mutate(
		.by = trigger
		, poll_duration = 1/(post_poll_time - pre_poll_time)
		, across(
			c(pre_poll_time,post_poll_time)
			, ~ c(NA,1/diff(.x))
			# , .names = '{.col}_diff'
		)
	)
	%>% drop_na()
	%>% select(trigger,contains('poll'))
	# %>% filter(post_poll_time<20)
	# %>% filter(post_poll_time<5)
	%>% pivot_longer(-trigger)
	%>% ggplot()
	+ facet_grid(
		. ~ name
		, scales = 'free_x'
	)
	+ geom_histogram(aes(x=value))
	+ labs(x='Hz')
	+ scale_x_log10()
)

(
	a
	%>% mutate(
		post_poll_time = post_poll_time - min(post_poll_time)
		, post_poll_time = post_poll_time*1e3
	)
	%>% mutate(
		.by = trigger
		, dt = c(0,diff(post_poll_time))
		, group = cumsum(dt>15)
	)
	%>% mutate(
		.by = c(trigger,group)
		, post_poll_time = post_poll_time - min(post_poll_time)
		, kind = case_when(
			all(diff(value)>0) ~ 'increasing'
			, all(diff(value)<0) ~ 'decreasing'
			, T ~ 'mixed'
		)
	)
) ->
	a

(
	a
	%>% ggplot()
	+ facet_grid(
		trigger ~ kind
	)
	+ geom_line(
		aes(
			x = post_poll_time
			, y = value
			# , colour = trigger
			, group = group
		)
	)
)


(
	a
	%>% mutate(row=1:n())
	%>% filter(kind=='increasing')
	%>% filter(trigger=='right')
	%>% filter(row>320,row<370)
)
(
	a
	%>% filter(kind=='increasing')
	%>% summarise(
		.by = c(trigger,group)
		, value = min(value)
	)
	%>% ggplot()
	+ geom_histogram(aes(x=value))
)



a = tbls$exp

(
	a
	%>% mutate(
		across(
			c(rt,error)
			, ~ case_when(
				.x==-999 ~ NA
				, TRUE ~ .x
			)
		)
		, recal_group = cumsum(recal)
	)
	%>% mutate(
		.by = c(block,recal_group)
		, across(
			c(flankers,simon,target)
			, ~ lag(.x)
			, .names = '{.col}_last'
		)
	)
	%>% filter(recal==0) # eliminates the first trial after a recalibration
	%>% select(-recal)
) ->
	a

(
	a
	%>% select(contains('flankers'),contains('simon'))
	%>% drop_na()
	%>% count(flankers,flankers_last,simon,simon_last)
)

(
	a
	# %>% rename(trial_num = trialNum)
	%>% select(trial_num,target_on_time0:target_on_time3)
	%>% pivot_longer(-trial_num)
	%>% arrange(name)
	%>% mutate(
		.by = trial_num
		, value = c(0,diff(value*1e3))
	)
	%>% filter(name!='target_on_time0') # bc artificially set as 0
	# %>% summarise(
	# 	value = mean(abs(value)<1e3)
	# ))
	%>% filter(abs(value)<1e3)
	%>% ggplot()
	+ facet_grid(name~.)
	+ geom_histogram(aes(x=value))
)

return(a)
}

