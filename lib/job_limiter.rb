module Cad
  # Caps concurrent worker jobs and the number of requests allowed to wait for a slot.
  class JobLimiter
    Busy = Class.new(StandardError)

    def initialize
      @mutex = Mutex.new
      @cond = ConditionVariable.new
      @running = 0
      @waiting = 0
    end

    def run
      acquire
      begin
        yield
      ensure
        release
      end
    end

    def stats
      @mutex.synchronize { { running: @running, waiting: @waiting, max_jobs: Config.max_jobs, max_queue: Config.max_queue } }
    end

    private

    def acquire
      @mutex.synchronize do
        raise Busy, "cad-render busy: #{@running} running, #{@waiting} waiting" if @running >= Config.max_jobs && @waiting >= Config.max_queue

        @waiting += 1
        @cond.wait(@mutex) while @running >= Config.max_jobs
        @waiting -= 1
        @running += 1
      end
    end

    def release
      @mutex.synchronize do
        @running -= 1
        @cond.signal
      end
    end
  end
end
